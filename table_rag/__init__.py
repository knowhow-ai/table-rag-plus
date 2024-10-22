import sqlite3
import json
import logging
import asyncio
import os
import sqlparse  # Importing SQLParse for query manipulation
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import DML, Keyword
from openai import AsyncOpenAI  # Assuming you're using OpenAI API for LLM
import json_repair
import re

LLM_API_SERVER = os.environ.get("LLM_API_SERVER", "http://localhost:11434/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "mistral-nemo")

logging.basicConfig(level=logging.INFO)

logging.info(f"Using LLM API Server: {LLM_API_SERVER}, model: {LLM_MODEL}")

# Helper function to load prompt templates
def load_prompt_template(file_path):
    with open(file_path, 'r') as file:
        return file.read()

class TableRAG:
    def __init__(self, db_path, llm_client, cell_encoding_budget=1000,retry_execute=3):
        self.db_path = db_path
        self.llm_client = llm_client
        self.cell_encoding_budget = cell_encoding_budget
        self.retry_execute = retry_execute 

        schema_keys = self.schema_retrieval()
        self.schema = schema_keys[0]
        self.foreign_keys = schema_keys[1]
        self.cell_database = self.build_cell_db()
        # Load prompt templates
        self.query_expansion_prompt_template = load_prompt_template('prompts/query_expansion.prompt')
        self.sql_generation_prompt_template = load_prompt_template('prompts/sql_generation.prompt')
        self.query_classification_prompt_template = load_prompt_template('prompts/query_classification.prompt')
        self.query_healing_prompt_template = load_prompt_template('prompts/query_healing.prompt')  # For query healing
        self.explain_result_prompt_template = load_prompt_template('prompts/explain_result.prompt')  # For result explanation

    def schema_retrieval(self, max_sample_length=100):
        logging.debug("Doing schema Retrieval")
        schema = {}
        foreign_keys = {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()

                schema[table_name] = {
                    "columns": [
                        {
                            "name": column[1],
                            "type": column[2],
                            "sample": None
                        } for column in columns
                    ]
                }

                # Extract foreign keys
                cursor.execute(f"PRAGMA foreign_key_list({table_name});")
                foreign_key_info = cursor.fetchall()

                foreign_keys[table_name] = [
                    {
                        "from": fk[3],  # local column
                        "to_table": fk[2],  # referenced table
                        "to": fk[4]  # referenced column
                    }
                    for fk in foreign_key_info
                ]

                # Get sample data
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 1;")
                sample_row = cursor.fetchone()

                if sample_row:
                    for idx, column in enumerate(schema[table_name]["columns"]):
                        sample_value = sample_row[idx]
                        if isinstance(sample_value, str) and len(sample_value) > max_sample_length:
                            column["sample"] = sample_value[:max_sample_length] + "..."
                        else:
                            column["sample"] = sample_value

            conn.close()

        except sqlite3.Error as e:
            logging.error(f"Failed to retrieve database schema: {e}")

        return schema, foreign_keys

    def schema_to_create_statements(self):
        create_statements = []
        
        # Retrieve schema and foreign key information
        schema, foreign_keys = self.schema_retrieval()

        for table_name, table_data in schema.items():
            columns = table_data["columns"]
            column_definitions = []
            
            for column in columns:
                column_definitions.append(f"{column['name']} {column['type']}")
            
            # Create the table definition statement
            create_statement = f"CREATE TABLE {table_name} ({', '.join(column_definitions)});"
            create_statements.append(create_statement)
            
            # Add samples as comments
            for column in columns:
                if column["sample"]:
                    create_statements.append(f"-- Sample: {column['name']} = {column['sample']}")
            
            # Add foreign key join hints as comments
            if table_name in foreign_keys:
                for fk in foreign_keys[table_name]:
                    join_comment = f"-- {table_name}.{fk['from']} can be joined with {fk['to_table']}.{fk['to']}"
                    create_statements.append(join_comment)
            
            # Optionally add inferred join hints based on naming convention (_id pattern)
            for column in columns:
                if column['name'].endswith('_id'):
                    inferred_table = column['name'][:-3]  # e.g., 'product_id' -> 'product'
                    join_comment = f"-- {table_name}.{column['name']} might join with {inferred_table}.id"
                    create_statements.append(join_comment)

        return "\n".join(create_statements)

    def build_cell_db(self):
        """
        Builds a database of distinct column-value pairs for cell retrieval.
        Only the most frequent/distinct values are kept, respecting the cell encoding budget.
        """
        cell_db = {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT * FROM {table_name} LIMIT {self.cell_encoding_budget};")
                rows = cursor.fetchall()

                if rows:
                    cell_db[table_name] = {}
                    for row in rows:
                        for idx, column in enumerate(row):
                            column_name = self.schema[table_name]["columns"][idx]["name"]
                            if column_name not in cell_db[table_name]:
                                cell_db[table_name][column_name] = set()
                            if len(cell_db[table_name][column_name]) < self.cell_encoding_budget:
                                cell_db[table_name][column_name].add(column)

            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Failed to build cell database: {e}")
        
        return cell_db

    def get_relevant_cells(self, table_name, columns, cell_values):
        """
        Retrieve relevant cells from the cell database based on columns and values.
        """
        relevant_cells = {}
        if table_name in self.cell_database:
            table_cells = self.cell_database[table_name]
            for column in columns:
                if column in table_cells:
                    # Only return cell values that match or are within the given column
                    relevant_cells[column] = list(table_cells[column].intersection(cell_values))
        return relevant_cells

    async def tabular_query_expansion(self, prompt):
        """
        Expands the query into smaller schema and cell-specific queries using external prompt template.
        """
        logging.info("Doing Query Expansion")

        # Use the external query_expansion.prompt template
        query_expansion_prompt = self.query_expansion_prompt_template.format(
            schema=self.schema_to_create_statements(),
            user_query=prompt
        )

        response = await self.llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": query_expansion_prompt}],
            stream=False
           # response_format=QueryExpansionResponse
        )

        response_text = response.choices[0].message.content.strip()

        logging.info(f"Query Expansion Response: {response_text}")  # Log full response for debugging

        try:
            # Extract the JSON part of the response (assuming it’s wrapped in ```json blocks)
            json_text = re.search(r'```json(.*?)```', response_text, re.DOTALL).group(1).strip()
            logging.info("Extracted JSON Data: " + json_text)
            expansion_data = json_repair.loads(json_text)
            
            
            # Use fallback for 'cell_values' in case it's missing
            columns = expansion_data.get("columns", [])
            cell_values = expansion_data.get("cell_values", expansion_data.get("possible_cell_values", []))

            # Log extracted columns and cell values for debugging
            logging.info(f"Extracted Columns: {columns}")
            logging.info(f"Extracted Cell Values: {cell_values}")
            
            return columns, cell_values

        except json.JSONDecodeError:
            raise ValueError("Failed to decode query expansion response")
        except KeyError as e:
            logging.error(f"Missing key in the expansion data: {e}")
            raise ValueError(f"Failed to extract necessary data: {str(e)}")


    async def generate_sql_query(self, natural_language_query):
        """
        Generate SQL query from natural language input using query expansion and retrieval.
        """
        # Step 1: Expand the query
        columns, cell_values = await self.tabular_query_expansion(natural_language_query)

        # Step 2: Get relevant cells from the cell database
        relevant_cells = {}
        for table_name in self.cell_database:
            relevant_cells[table_name] = self.get_relevant_cells(table_name, columns, cell_values)

        # Step 3: Use the relevant cells for query generation
        sql_prompt = self.sql_generation_prompt_template.format(
            schema=self.schema_to_create_statements(),
            user_query=natural_language_query,
            columns=columns,
            cell_values=json.dumps(relevant_cells, indent=4)
        )

        logging.info(sql_prompt)

        response = await self.llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": sql_prompt}],
            stream=False
        )

        sql_query = response.choices[0].message.content.strip()
        logging.info("Generated SQL Query: " + sql_query)

        sql_query = re.search(r'```sql(.*?)```', sql_query, re.DOTALL).group(1).strip()
        
        logging.info("Extracted SQL Query: " + sql_query)

        # Parse and refine SQL query
        return sql_query


    async def is_natural_language_query(self, input_text):
        """
        Determine if the input is a natural language query.
        """
        # Use the external query_classification.prompt template
        classification_prompt = self.query_classification_prompt_template.format(input_text=input_text)

        response = await self.llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": classification_prompt}],
            stream=False
        )

        return response.choices[0].message.content.strip() == "Natural Language Query"

    async def execute_sql_query(self, sql_query):
        """
        Executes an SQL query and retries up to self.retry_execute times if errors occur. 
        Uses the LLM to try and fix the query.
        """
        attempt = 0
        last_error = None

        while attempt < self.retry_execute:
            try:
                logging.info(f"Executing SQL query (Attempt {attempt + 1}/{self.retry_execute}): {sql_query}")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(sql_query)  # Ensure sql_query is a string, not coroutine
                results = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                conn.close()
                return results, columns  # Successful execution
            except sqlite3.Error as e:
                last_error = str(e)
                logging.error(f"Failed to execute query (Attempt {attempt + 1}): {e}")

                # Send the error and original query to the LLM for healing, and await it
                sql_query = await self.heal_sql_query(sql_query, last_error)  # Await the coroutine

                # If the LLM did not provide a valid correction, break the loop
                if not sql_query:
                    logging.error("No valid correction from LLM. Stopping retry attempts.")
                    break

            attempt += 1

        # If all retries failed, return the last error encountered
        logging.error(f"Failed to execute the query after {self.retry_execute} attempts.")
        return None, None

    async def heal_sql_query(self, failed_query, error_message):
        """
        Sends the failed SQL query and error message to the LLM, asking for a correction.
        """
        try:
            # Prepare the prompt using the healing prompt template
            healing_prompt = self.query_healing_prompt_template.format(
                original_query=failed_query,
                error_message=error_message,
                schema=self.schema_to_create_statements()
            )

            logging.info(f"Sending query healing prompt to LLM: {healing_prompt}")

            # Send the prompt to the LLM to generate a corrected SQL query
            response = await self.llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": healing_prompt}],
                stream=False
            )

            # Extract the corrected SQL query from the LLM response
            corrected_query = response.choices[0].message.content.strip()

            logging.info(f"Received corrected SQL query: {corrected_query}")

            # Extract SQL from code block (if it's inside a code block)
            corrected_query = re.search(r'```sql(.*?)```', corrected_query, re.DOTALL)
            if corrected_query:
                return corrected_query.group(1).strip()

            return corrected_query  # Return the corrected query
        except Exception as e:
            logging.error(f"Failed to heal SQL query: {e}")
            return None  # Return None if healing fails
        
    async def explain_result(self, result, prompt):
        """
        Explains the result of a query using the LLM.
        """
        # Prepare the prompt using the explain_result prompt template
        explain_prompt = self.explain_result_prompt_template.format(
            query=prompt,
            result=result
        )

        logging.info(f"Sending explain result prompt to LLM: {explain_prompt}")

        # Send the prompt to the LLM to generate an explanation
        response = await self.llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": explain_prompt}],
            stream=False
        )

        explanation = response.choices[0].message.content.strip()

        logging.info(f"Received explanation: {explanation}")

        return explanation

