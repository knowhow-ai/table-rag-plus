import logging
import asyncio
import os
import chainlit as cl
from table_rag import TableRAG
from openai import AsyncOpenAI  # Assuming you're using OpenAI API for LLM
from tabulate import tabulate

LLM_API_SERVER = os.environ.get("LLM_API_SERVER", "http://localhost:11434/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")
LLM_MODEL = os.environ.get("LLM_MODEL", "mistral-nemo")


logging.basicConfig(level=logging.INFO)

client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_API_SERVER)

db_path = 'bbq_manufacturing.db'
table_rag = TableRAG(db_path, client)

# Step for generating SQL query
@cl.step(type="tool")
async def generate_sql_query(prompt: str):
    try:
        sql_query = await table_rag.generate_sql_query(prompt)
        return {"sql_query": sql_query}
    except Exception as e:
        logging.error(f"Error generating SQL query: {e}")
        return {"error": str(e)}

# Step for executing SQL query
@cl.step(type="tool")
async def execute_sql_query(prompt: str, sql_query: str):
    try:
        result_tuple = await table_rag.execute_sql_query(prompt, sql_query)
        return {"results": result_tuple[0], "columns": result_tuple[1]}
    except Exception as e:
        logging.error(f"Error executing SQL query: {e}")
        return {"error": str(e)}

# Step for explaining result
@cl.step(type="tool")
async def explain_result(result, prompt):
    try:
        explanation = await table_rag.explain_result(result, prompt)
        return {"explanation": explanation}
    except Exception as e:
        logging.error(f"Error explaining result: {e}")
        return {"error": str(e)}

# Step for digging deeper into the result
@cl.step(type="tool")
async def dig_deeper(sql_query: str, result, prompt: str, explanation: str):
    try:
        dig_deeper_sql = await table_rag.dig_deeper(sql_query, result, prompt, explanation)
        return {"dig_deeper_sql": dig_deeper_sql}
    except Exception as e:
        logging.error(f"Error digging deeper: {e}")
        return {"error": str(e)}

# Define what happens when a message is received
@cl.on_message
async def main(message: cl.Message):
    prompt = message.content

    try:
        # Generate the SQL query
        sql_query_result = await generate_sql_query(prompt)
        if "error" in sql_query_result:
            await cl.Message(content=f"Error: {sql_query_result['error']}").send()
            return

        sql_query = sql_query_result["sql_query"]
        await cl.Message(content=f"```sql\n{sql_query}\n```").send()

        # Execute the SQL query
        result_tuple = await execute_sql_query(prompt, sql_query)
        if "error" in result_tuple:
            await cl.Message(content=f"Error: {result_tuple['error']}").send()
            return

        results, columns = result_tuple["results"], result_tuple["columns"]
        if results:
            result_table = tabulate(results, headers=columns, tablefmt="github")
            await cl.Message(content=result_table).send()
            table_rag.add_message({"role":"assistant", "content": result_table})

            # Explain the result
            explanation_result = await explain_result(result_table, prompt)
            if "error" in explanation_result:
                await cl.Message(content=f"Error: {explanation_result['error']}").send()
                return

            explanation = explanation_result["explanation"]
            table_rag.add_message({"role":"assistant", "content": explanation})
            await cl.Message(content=f"Explanation: {explanation}").send()

            # Dig deeper into the result
            dig_deeper_result = await dig_deeper(sql_query, result_table, prompt, explanation)
            if "error" in dig_deeper_result:
                await cl.Message(content=f"Error: {dig_deeper_result['error']}").send()
                return

            dig_deeper_sql = dig_deeper_result["dig_deeper_sql"]
            deeper_result_tuple = await execute_sql_query(prompt, dig_deeper_sql)
            if "error" in deeper_result_tuple:
                await cl.Message(content=f"Error: {deeper_result_tuple['error']}").send()
                return
          
                
            try:
                deeper_results, deeper_columns = deeper_result_tuple["results"], deeper_result_tuple["columns"]
                deeper_result_table = tabulate(deeper_results, headers=deeper_columns, tablefmt="github")
                table_rag.add_message({"role":"assistant", "content": deeper_result_table})
                await cl.Message(content=f"Deeper Result:\n{deeper_result_table}").send()

                # Explain the deeper result
                deeper_explanation_result = await explain_result(deeper_results, prompt)
                if "error" in deeper_explanation_result:
                    # send just the explain
                    #await cl.Message(content=f"Error: {deeper_explanation_result['error']}").send()
                    return
                else:
                    deeper_explanation = deeper_explanation_result["explanation"]
                    await cl.Message(content=f"Deeper Explanation: {deeper_explanation}").send()
                    table_rag.add_message({"role":"assistant", "content": deeper_explanation})
            except Exception as e:
                return

    except ValueError as e:
        await cl.Message(content=f"...").send()
