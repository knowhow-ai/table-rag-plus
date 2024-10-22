
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
    
    db_path = 'bbq_manufacturing.db'

    table_rag = TableRAG(db_path, client)

    async def run():
        while True:
            try:
                prompt = input("Enter a natural language query: ")
                sql_query = await table_rag.generate_sql_query(prompt)
                

                result_tuple = await table_rag.execute_sql_query(prompt, sql_query)
                results, columns = result_tuple
                if results:
                    result = tabulate(results, headers=columns, tablefmt="grid")
                    table_rag.add_message({"role":"assistant", "content": result})
                    # Use tabulate to print the table
                    print(result)

                    explanation = await table_rag.explain_result(result, prompt)

                    # dig deeper
                    try:
                        dig_deeper_sql = await table_rag.dig_deeper(sql_query, result, prompt, explanation)

                        result_tuple = await table_rag.execute_sql_query(prompt, dig_deeper_sql)
                        results, columns = result_tuple

                        explanation = await table_rag.explain_result(results, prompt)
                        
                    except Exception as e:
                        logging.error(f"Error in dig deeper: {e}")

                    print("Explanation:\n", explanation)


                print("\n")
            except ValueError as e:
                print(f"Error: {e}")

    asyncio.run(run())
