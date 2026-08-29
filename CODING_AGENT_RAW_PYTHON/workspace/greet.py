import sys

# Check if a name was provided as a command line argument
if len(sys.argv) != 2:
    print("Usage: python greet.py <name>")
    sys.exit(1)

# Get the name from the command line argument
name = sys.argv[1]

# Print the greeting
print(f"Hello, {name}!")