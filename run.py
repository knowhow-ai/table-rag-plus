
import logging
import asyncio
import os
from table_rag import TableRAG
from openai import AsyncOpenAI  # Assuming you're using OpenAI API for LLM
from tabulate import tabulate

LLM_API_SERVER = os.environ.get("LLM_API_SERVER", "http://localhost:11434/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "mistral-nemo")

logging.basicConfig(level=logging.INFO)



if __name__ == "__main__":
    client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_SERVER)
    
    db_path = 'employee_database.db'

    table_rag = TableRAG(db_path, client)

    async def run():
        while True:
            try:
                prompt = input("Enter a natural language query: ")
                sql_query = await table_rag.generate_sql_query(prompt)
                print("Generated SQL Query:", sql_query)

                result_tuple = await table_rag.execute_sql_query(prompt, sql_query)
                results, columns = result_tuple
                if results:
                    result = tabulate(results, headers=columns, tablefmt="grid")
                    
                    # Use tabulate to print the table
                    print(result)

                    explanation = await table_rag.explain_result(result, prompt)

                    print("Explanation:\n", explanation)


                print("\n")
            except ValueError as e:
                print(f"Error: {e}")

    asyncio.run(run())
