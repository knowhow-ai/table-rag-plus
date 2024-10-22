import sqlite3
from datetime import timedelta, datetime
import random
from faker import Faker
fake = Faker()
# Define custom positions and departments relevant to the BBQ manufacturing company
departments = [
    ('Sales', 'Handles customer relations and product sales'),
    ('Human Resources', 'Manages employee relations, recruitment, and compliance'),
    ('Engineering', 'Designs and improves product features and manufacturing processes'),
    ('Marketing', 'Promotes products and manages brand reputation'),
    ('Production', 'Manufactures the products, manages quality control and assembly'),
    ('Supply Chain', 'Handles procurement of raw materials, logistics, and inventory management')
]

positions_by_department = {
    'Sales': ['Sales Representative', 'Account Manager', 'Regional Sales Manager'],
    'Human Resources': ['HR Manager', 'Recruitment Specialist', 'Compliance Officer'],
    'Engineering': ['Mechanical Engineer', 'Product Designer', 'Quality Assurance Engineer'],
    'Marketing': ['Marketing Coordinator', 'Social Media Manager', 'Product Marketing Manager'],
    'Production': ['Production Line Worker', 'Assembly Technician', 'Production Manager'],
    'Supply Chain': ['Procurement Specialist', 'Logistics Coordinator', 'Inventory Manager']
}

products = [
    ('BBQ Grill', 399.99, 200.00),
    ('BBQ Cover', 29.99, 10.00),
    ('BBQ Utensils', 19.99, 5.00),
    ('BBQ Sauce', 4.99, 2.00),
    ('Charcoal Bag', 14.99, 6.00),
    ('Grill Brush', 12.99, 4.00)
]

# Create a connection to the database
conn = sqlite3.connect('bbq_manufacturing.db')

# Create a cursor object using the cursor() method
cursor = conn.cursor()

# Turn on foreign key support
cursor.execute("PRAGMA foreign_keys = ON")

# Create Department table
cursor.execute('''
CREATE TABLE Department (
    department_id INTEGER PRIMARY KEY,
    department_name TEXT,
    department_description TEXT
);''')

# Insert custom departments
cursor.executemany("INSERT INTO Department (department_name, department_description) VALUES (?, ?)", departments)

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

# Generate realistic employee data using LLM insights
def generate_employees(num_employees):
    employee_data = []
    for _ in range(num_employees):
        # Randomize department and position
        department_id = random.randint(1, len(departments))
        department_name = departments[department_id - 1][0]
        position = random.choice(positions_by_department[department_name])
        
        # Generate realistic salary based on department and position
        salary = random.uniform(35000, 120000) if department_name != 'Production' else random.uniform(30000, 70000)

        hire_date = datetime.now() - timedelta(days=random.randint(100, 3650))  # Random hire date within 10 years
        termination_date = hire_date + timedelta(days=random.randint(365, 1825)) if random.random() < 0.3 else None
        # use faker for names

        first_name = fake.first_name()
        last_name = fake.last_name()
        
        employee_data.append((first_name, last_name, department_id, position, salary, hire_date, termination_date))
    
    return employee_data

# Insert employees into the database
employees = generate_employees(50)
cursor.executemany('''
    INSERT INTO Employees (first_name, last_name, department_id, position, salary, hire_date, termination_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', employees)

# Create Products table
cursor.execute('''
CREATE TABLE Products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT,
    price REAL,
    cost REAL
);''')

# Insert custom products
cursor.executemany("INSERT INTO Products (product_name, price, cost) VALUES (?, ?, ?)", products)

# Create Sales table
cursor.execute('''
CREATE TABLE Sales (
    sales_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    sale_price REAL,
    sale_date DATE,
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
);''')

# Generate realistic sales data
def generate_sales(num_sales):
    sales_data = []
    for _ in range(num_sales):
        employee_id = random.randint(1, len(employees))
        product_id = random.randint(1, len(products))
        quantity = random.randint(1, 20)
        sale_price = products[product_id - 1][1] * random.uniform(0.9, 1.1)  # Slight variation in sales prices
        sale_date = datetime.now() - timedelta(days=random.randint(1, 365))
        
        sales_data.append((employee_id, product_id, quantity, sale_price, sale_date))
    
    return sales_data

# Insert sales into the database
sales = generate_sales(500)
cursor.executemany('''
    INSERT INTO Sales (employee_id, product_id, quantity, sale_price, sale_date)
    VALUES (?, ?, ?, ?, ?)
''', sales)

# Create ClockInClockOut table
cursor.execute('''
CREATE TABLE ClockInClockOut (
    clock_id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    clock_in DATETIME,
    clock_out DATETIME,
    FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
);''')

# Generate clock-in/clock-out records
def generate_clock_in_out(num_records):
    clock_data = []
    for _ in range(num_records):
        employee_id = random.randint(1, len(employees))
        clock_in = datetime.now() - timedelta(days=random.randint(1, 30), hours=random.randint(8, 9))
        clock_out = clock_in + timedelta(hours=random.uniform(7, 9))  # Shift duration between 7-9 hours
        
        clock_data.append((employee_id, clock_in, clock_out))
    
    return clock_data

# Insert clock-in/out records into the database
clock_in_out = generate_clock_in_out(1000)
cursor.executemany('''
    INSERT INTO ClockInClockOut (employee_id, clock_in, clock_out)
    VALUES (?, ?, ?)
''', clock_in_out)

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

# Generate realistic payroll data
def generate_payroll(num_records):
    payroll_data = []
    for _ in range(num_records):
        employee_id = random.randint(1, len(employees))
        pay_period_start = datetime.now() - timedelta(days=random.randint(1, 30))
        pay_period_end = pay_period_start + timedelta(days=14)  # 2-week pay period
        hours_worked = random.uniform(70, 80)  # Full-time hours
        gross_pay = hours_worked * random.uniform(20, 60)  # Based on an hourly rate
        deductions = gross_pay * random.uniform(0.1, 0.25)  # Deductions between 10-25%
        net_pay = gross_pay - deductions
        
        payroll_data.append((employee_id, pay_period_start, pay_period_end, hours_worked, gross_pay, deductions, net_pay))
    
    return payroll_data

# Insert payroll data into the database
payroll = generate_payroll(1000)
cursor.executemany('''
    INSERT INTO Payroll (employee_id, pay_period_start, pay_period_end, hours_worked, gross_pay, deductions, net_pay)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', payroll)

# Commit the changes and close the connection
conn.commit()
conn.close()
