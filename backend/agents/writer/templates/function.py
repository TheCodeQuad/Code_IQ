"""
Function documentation template
"""

class FunctionTemplate:
    """Template for function documentation"""
    
    @staticmethod
    def get_google_template() -> str:
        return """{summary}

{description}

Args:
{parameters}

Returns:
{returns}

{raises}

{examples}

{notes}
"""
    
    @staticmethod
    def get_numpy_template() -> str:
        return """{summary}

{description}

Parameters
----------
{parameters}

Returns
-------
{returns}

{raises}

{examples}

{notes}
"""
    
    @staticmethod
    def get_sphinx_template() -> str:
        return """{summary}

{description}

{parameters}

{returns}

{raises}

{examples}
"""