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
    def __init__(self, db_path, llm_client, cell_encoding_budget=1000):
        self.db_path = db_path
        self.llm_client = llm_client
        self.cell_encoding_budget = cell_encoding_budget
        self.schema = self.schema_retrieval()
        self.cell_database = self.build_cell_db()

        # Load prompt templates
        self.query_expansion_prompt_template = load_prompt_template('prompts/query_expansion.prompt')
        self.sql_generation_prompt_template = load_prompt_template('prompts/sql_generation.prompt')
        self.query_classification_prompt_template = load_prompt_template('prompts/query_classification.prompt')

    def schema_retrieval(self, max_sample_length=100):
        logging.debug("Doing schema Retrieval")
        schema = {}
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

        return schema

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
            schema=json.dumps(self.schema, indent=4),
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
            schema=json.dumps(self.schema, indent=4),
            user_query=natural_language_query,
            columns=columns,
            cell_values=json.dumps(relevant_cells, indent=4)
        )

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

    # def refine_sql_query(self, parsed_query, columns):
    #     """
    #     Refines the SQL query by using sqlparse to validate, restructure, or optimize it.
    #     If sqlparse fails, skip refinement and log the error.
    #     """
    #     try:
    #         new_query = []

    #         for token in parsed_query.tokens:
    #             if token.ttype is DML and token.value.upper() == 'SELECT':
    #                 new_query.append(token.value)

    #                 # Use token_next correctly to get the next token after SELECT
    #                 next_token_tuple = parsed_query.token_next(parsed_query.token_index(token))
    #                 if next_token_tuple:  # Ensure token_next found a token
    #                     next_token = next_token_tuple[1]
    #                     # Replace * with the actual columns retrieved by query expansion
    #                     if isinstance(next_token, Identifier) or isinstance(next_token, IdentifierList):
    #                         new_query.append(f" {', '.join(columns)} ")
    #                     else:
    #                         new_query.append(str(next_token))
    #                 else:
    #                     # If no next token, fallback to the original token
    #                     new_query.append(token.value)
    #             else:
    #                 new_query.append(str(token))

    #         refined_query = ' '.join(new_query)
    #         return refined_query

    #     except Exception as e:
    #         # If sqlparse fails, log the error and skip refinement
    #         logging.error(f"Failed to refine SQL query using sqlparse: {e}")
    #         logging.info("Falling back to unrefined SQL query")
    #         # Fallback: return the unmodified query as a string
    #         return ' '.join(str(token) for token in parsed_query.tokens)



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

    def execute_sql_query(self, sql_query):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            conn.close()
            return results, columns
        except sqlite3.Error as e:
            logging.error(f"Failed to execute query: {e}")
            return None, None

