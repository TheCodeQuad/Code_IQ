
def helper(x: int) -> int:
    """Helper function"""
    return x * 2

def process(data: int) -> int:
    """Process data using helper"""
    result = helper(data)
    return result + 10

class Calculator:
    """Calculator class"""
    
    def compute(self, value: int) -> int:
        """Compute using helper"""
        return helper(value)
    
    def run(self, value: int) -> int:
        """Run computation"""
        computed = self.compute(value)
        return process(computed)

async def main(value: int) -> int:
    """Main entry point"""
    calc = Calculator()
    result = calc.run(value)
    return result
