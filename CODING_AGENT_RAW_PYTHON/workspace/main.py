import json
import os

TODO_FILE = 'todos.json'

# Ensure the JSON file exists with an empty list
if not os.path.exists(TODO_FILE):
    with open(TODO_FILE, 'w') as file:
        json.dump([], file)

# Function to add a new todo
def add_todo(todo):
    with open(TODO_FILE, 'r') as file:
        todos = json.load(file)
    if todo not in todos:
        todos.append(todo)
    with open(TODO_FILE, 'w') as file:
        json.dump(todos, file)

# Function to list all todos
def list_todos():
    with open(TODO_FILE, 'r') as file:
        todos = json.load(file)
    return todos

# Function to delete a todo by its number

def delete_todo(index):
    with open(TODO_FILE, 'r') as file:
        todos = json.load(file)
    if 0 <= index < len(todos):
        removed = todos.pop(index)
        with open(TODO_FILE, 'w') as file:
            json.dump(todos, file)
        return removed
    return None


# Main program interface
if __name__ == '__main__':
    print('Please run the add functionality to input your todos.')
    print('Todos currently in list:')
    todos = list_todos()
    for item in todos:
        print(f'- {item}')
    print('Exiting...')