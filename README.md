

# 🌟 **Table-rag+: A Self-Healing Query Generator for Tabular Data** 🌟

**Table-rag+** is a naive implementation of an advanced, self-healing framework for understanding large-scale tables using language models (LMs). It extends upon the ideas introduced in the [TableRAG paper](https://arxiv.org/abs/2410.04739v1) by incorporating schema and cell retrieval, query expansion, and enhanced error-handling mechanisms, making it suitable for complex table queries. This is the **first version** of **table-rag+** and is designed for **SQLite databases** but not yet optimized for large-scale datasets. Future research will focus on scaling this system to handle larger environments and more complex queries.

---

## ✨ **Key Features**

- **🔄 Tabular Query Expansion**: Automatically expands user queries to suggest the most relevant columns and cell values.
- **🔑 Foreign Key Detection**: Extracts foreign key relationships between tables and provides intelligent suggestions for joins.
- **📊 Cell Database**: Builds an efficient database of distinct column-value pairs to retrieve relevant cells, improving query accuracy.
- **⚡ Self-Healing SQL Execution**: When an SQL query fails, the system automatically attempts to heal the query and retries execution up to **three times**.
- **🤖 Integration with Mistral-Nemo (Ollama)**: Uses *Mistral-Nemo* via the *Ollama* API to process natural language and generate optimized SQL queries.
- **🛠️ Contextual Query Repair**: Automatically logs errors and regenerates SQL queries based on feedback from the database system.
- **📜 Prompt-Based Query Generation**: Manages prompt templates with external `.prompt` files for easy updates and customization.
- **📈 Efficient Query Processing**: Utilizes schema and cell retrieval to minimize token complexity and ensure efficient large table processing.

---

## ⚙️ **Installation**

### 📋 **Prerequisites**
- 🐍 Python 3.7+
- 📦 Poetry for dependency management
- 🗄️ SQLite3 (usually included with Python)
- 🧠 [**Ollama**](https://ollama.com/) with [**Mistral-Nemo**](https://ollama.com/library/mistral-nemo) model 

### 🚀 **Step-by-Step Setup**

1. **Clone the Repository**:
   ```bash
   git clone git@github.com:knowhow-ai/table-rag-plus.git
   cd table-rag-plus
   ```

2. **Install Dependencies Using Poetry**:
   ```bash
   poetry install
   ```

3. **Set Environment Variables**:
   ```bash
   export LLM_API_SERVER="http://localhost:11434/v1"
   export LLM_API_KEY="ollama"
   export LLM_MODEL="mistral-nemo"
   ```

4. **Install SQLite (if not already installed)**:
   ```bash
   sudo apt-get install sqlite3
   ```

---

## 🖥️ **Usage**

To run the main script and generate SQL queries from natural language prompts:

```bash
poetry run python run.py
```

You will be prompted to input natural language queries, which will be translated into SQL and executed against the SQLite database.

### ⚡ **Self-Healing Feature**

If a query fails during execution, **table-rag+** will:
1. Attempt to heal the query using an LLM.
2. Retry execution up to **three times**.
3. Return an error if the retries are unsuccessful.

### ✨ **Example**

```python
async def run():
    prompt = "What is the average salary of employees in the HR department?"
    sql_query = await table_rag.generate_sql_query(prompt)
    result_tuple = await table_rag.execute_sql_query(sql_query)
    print(result_tuple)
```

Upon input, the system will generate a corresponding SQL query and attempt to execute it, correcting any errors if necessary.

---

## 📚 **References**

This project builds upon the concepts introduced in the following research paper:

- 📄 **Si-An Chen, Lesly Miculicich, Julian Martin Eisenschlos, et al.**  
  "TableRAG: Million-Token Table Understanding with Language Models."  
  38th Conference on Neural Information Processing Systems (NeurIPS 2024).  
  [**arXiv:2410.04739v1**](https://arxiv.org/abs/2410.04739v1)

---

## 🚀 **Future Improvements**

### 🔨 **Work in Progress**
This is the **first version** of **table-rag+**. It currently works only with **SQLite databases** and is **not optimized for large-scale datasets**. Here are some exciting improvements we have planned:

- **🤖 Auto-Prompt Generation for SQLite and Other Data Sources**: 
  - Automatic generation of optimized prompts based on database structure, starting with **SQLite**.
- **🔍 Retrieval-Augmented Generation (RAG) Support**:
  - Integrate **RAG** to enhance the system’s ability to answer questions by retrieving relevant documents alongside database queries.
- **🔄 Move to SQLAlchemy**:
  - Expand beyond **SQLite** to support multiple databases by adopting **SQLAlchemy**, allowing integration with PostgreSQL, MySQL, and more.
- **🛠️ Advanced Error Diagnostics**:
  - Provide granular feedback on why specific SQL queries fail and offer detailed diagnostics for better debugging and correction.
- **🌐 Distributed Processing**:
  - Scale the system across multiple databases and table structures to create a robust solution for enterprise-level use cases.

---

By using **table-rag+**, you can efficiently process natural language queries on tabular data, benefiting from advanced error-handling and query generation capabilities. Stay tuned as we continue to improve and scale this project! 🚀✨

---

If you have any questions, suggestions, or ideas for contributions, feel free to submit a pull request or reach out! 😊