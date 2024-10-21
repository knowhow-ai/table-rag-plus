
import logging
import asyncio
import os
from table_rag import TableRAG
from openai import AsyncOpenAI  # Assuming you're using OpenAI API for LLM


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

                results, columns = table_rag.execute_sql_query(sql_query)
                if results:
                    print("\nResults:")
                    header = " | ".join(columns)
                    for row in results:
                        print(row)
            except ValueError as e:
                print(f"Error: {e}")

    asyncio.run(run())
