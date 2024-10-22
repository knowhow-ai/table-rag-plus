"""
Create a SQLite database for a fictional manufacturing company that makes bbqs and accessory.

The database should have the following tables:
Employees,
Department,
Sales,
ClockInClockOut,
Payroll,
Product


"""

import sqlite3

# Create a connection to the database
conn = sqlite3.connect('employee_database.db')

# Create a cursor object using the cursor() method
cursor = conn.cursor()

# Turn on foreign key support
cursor.execute("PRAGMA foreign_keys = ON")

# Create Employees table
cursor.execute('''
CREATE TABLE Employees (
    employee_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    department_id INTEGER,
    position TEXT,
    salary REAL,
    hire_date DATE,
    termination_date DATE,
    FOREIGN KEY (department_id) REFERENCES Department(department_id)
);''')

# Create Department table

cursor.execute('''
CREATE TABLE Department (
    department_id INTEGER PRIMARY KEY,
    department_name TEXT
);''')

# Create Product table
cursor.execute('''
CREATE TABLE Products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT,
    price REAL,
    cost REAL
);''')

# Create Sales table
cursor.execute('''
CREATE TABLE Sales (
    sales_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    price REAL,
    date DATE,
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
);''')

# Create ClockInClockOut table
cursor.execute('''
CREATE TABLE ClockInClockOut (
    clock_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    clock_in DATETIME,
    clock_out DATETIME,
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
);''')

# Create Payroll table
cursor.execute('''
CREATE TABLE Payroll (
    payroll_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    pay_period_start DATE,
    pay_period_end DATE,
    hours_worked REAL,
    gross_pay REAL,
    deductions REAL,
    net_pay REAL,
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
);''')

# Commit the changes
conn.commit()

# Generate some sample data

# Insert departments Sales, HR, Engineering, and Marketing

cursor.execute("INSERT INTO Department (department_name) VALUES ('Sales')")
cursor.execute("INSERT INTO Department (department_name) VALUES ('HR')")
cursor.execute("INSERT INTO Department (department_name) VALUES ('Engineering')")
cursor.execute("INSERT INTO Department (department_name) VALUES ('Marketing')")

# Use faker to create some employees
from faker import Faker

fake = Faker()

for _ in range(50):
    first_name = fake.first_name()
    last_name = fake.last_name()
    department_id = fake.random_int(min=1, max=4)
    position = fake.job()
    salary = fake.random_int(min=30000, max=100000)
    hire_date = fake.date_this_decade()
    termination_date = fake.date_this_decade()
    
    cursor.execute("INSERT INTO Employees (first_name, last_name, department_id, position, salary, hire_date, termination_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (first_name, last_name, department_id, position, salary, hire_date, termination_date))
    

# Insert some products
cursor.execute("INSERT INTO Products (product_name, price, cost) VALUES ('BBQ Grill', 399.99, 200.00)")
cursor.execute("INSERT INTO Products (product_name, price, cost) VALUES ('BBQ Cover', 29.99, 10.00)")
cursor.execute("INSERT INTO Products (product_name, price, cost) VALUES ('BBQ Utensils', 19.99, 5.00)")
cursor.execute("INSERT INTO Products (product_name, price, cost) VALUES ('BBQ Sauce', 4.99, 2.00)")

# Insert some sales with some trend data and employees should only be from Sales 
for _ in range(5400):
    employee_id = fake.random_int(min=1, max=50)
    product_id = fake.random_int(min=1, max=4)
    quantity = fake.random_int(min=1, max=10)
    price = fake.random_int(min=10, max=50)
    date = fake.date_this_decade()
    
    cursor.execute("INSERT INTO Sales (employee_id, product_id, quantity, price, date) VALUES (?, ?, ?, ?, ?)",
                   (employee_id, product_id, quantity, price, date))

    
# Insert some clock in/out records from 

for _ in range(1000):
    employee_id = fake.random_int(min=1, max=50)
    clock_in = fake.date_time_this_decade()
    clock_out = fake.date_time_this_decade()
    
    cursor.execute("INSERT INTO ClockInClockOut (employee_id, clock_in, clock_out) VALUES (?, ?, ?)",
                   (employee_id, clock_in, clock_out))
    

# Insert some payroll records
for _ in range(1000):
    employee_id = fake.random_int(min=1, max=50)
    pay_period_start = fake.date_this_decade()
    pay_period_end = fake.date_this_decade()
    hours_worked = fake.random_int(min=20, max=80)
    gross_pay = fake.random_int(min=500, max=2000)
    deductions = fake.random_int(min=50, max=500)
    net_pay = gross_pay - deductions
    
    cursor.execute("INSERT INTO Payroll (employee_id, pay_period_start, pay_period_end, hours_worked, gross_pay, deductions, net_pay) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (employee_id, pay_period_start, pay_period_end, hours_worked, gross_pay, deductions, net_pay))
    

# Commit the changes
conn.commit()