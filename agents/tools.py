from langchain_core.tools import tool
import datetime

@tool
def calculator(expression: str) -> str:
    """Useful for performing mathematical calculations. 
    Input should be a valid Python mathematical expression (e.g., '15 * 240 / 100')."""
    try:
        # Safe eval of mathematical expressions only
        allowed_names = {"abs": abs, "round": round}
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating: {e}"

@tool
def get_current_time() -> str:
    """Returns the current date and time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
