
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

def multiply(x: int, y: int) -> int:
    """Multiply two numbers"""
    result = add(x, x) * y
    return result

class Calculator:
    """A simple calculator class"""
    
    def __init__(self):
        """Initialize calculator"""
        self.history = []
    
    def calculate(self, operation: str, a: int, b: int) -> int:
        """Perform calculation"""
        if operation == "add":
            return add(a, b)
        elif operation == "multiply":
            return multiply(a, b)
        return 0

async def async_function(data: list) -> dict:
    """Example async function"""
    result = {}
    for item in data:
        result[item] = multiply(item, 2)
    return result
