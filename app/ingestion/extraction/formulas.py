"""Mathematical formula semantic extraction."""

import re


def detect_formula(text: str) -> list[dict[str, str]]:
    """
    Detect mathematical formulas in text.

    Args:
        text: Input text

    Returns:
        List of dicts with 'formula', 'type', 'position'
    """
    formulas = []

    # LaTeX inline formulas: $...$
    inline_pattern = r"\$([^\$]+)\$"
    for match in re.finditer(inline_pattern, text):
        formulas.append(
            {"formula": match.group(1), "type": "latex_inline", "position": match.start(), "raw": match.group(0)}
        )

    # LaTeX display formulas: $$...$$
    display_pattern = r"\$\$([^\$]+)\$\$"
    for match in re.finditer(display_pattern, text):
        formulas.append(
            {"formula": match.group(1), "type": "latex_display", "position": match.start(), "raw": match.group(0)}
        )

    # Common mathematical expressions
    # Pattern: E = mc^2, F = ma, etc.
    equation_pattern = r"\b([A-Z])\s*=\s*([^\s,;.]+(?:\s*[+\-*/^]\s*[^\s,;.]+)*)\b"
    for match in re.finditer(equation_pattern, text):
        formulas.append(
            {"formula": match.group(0), "type": "equation", "position": match.start(), "raw": match.group(0)}
        )

    return formulas


def formula_to_text(formula: str, formula_type: str = "latex") -> str:
    """
    Convert formula to natural language description.

    Args:
        formula: Formula string
        formula_type: Type of formula (latex, equation, etc.)

    Returns:
        Natural language description
    """
    if formula_type == "latex_inline" or formula_type == "latex_display":
        return latex_to_text(formula)
    elif formula_type == "equation":
        return equation_to_text(formula)
    else:
        return formula


def latex_to_text(latex: str) -> str:
    """
    Convert LaTeX formula to text description.

    Args:
        latex: LaTeX formula

    Returns:
        Text description
    """
    # Simple conversions
    conversions = {
        r"\\frac\{([^}]+)\}\{([^}]+)\}": r"\1 divided by \2",
        r"\\sqrt\{([^}]+)\}": r"square root of \1",
        r"\\sum": "sum",
        r"\\int": "integral",
        r"\\alpha": "alpha",
        r"\\beta": "beta",
        r"\\gamma": "gamma",
        r"\\delta": "delta",
        r"\\pi": "pi",
        r"\\theta": "theta",
        r"\^2": " squared",
        r"\^3": " cubed",
        r"\^": " to the power of ",
        r"_": " subscript ",
    }

    text = latex
    for pattern, replacement in conversions.items():
        text = re.sub(pattern, replacement, text)

    # Remove remaining LaTeX commands
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"[{}]", "", text)

    return text.strip()


def equation_to_text(equation: str) -> str:
    """
    Convert simple equation to text.

    Args:
        equation: Equation string (e.g., "E = mc^2")

    Returns:
        Text description
    """
    # Parse equation
    parts = equation.split("=")
    if len(parts) != 2:
        return equation

    left = parts[0].strip()
    right = parts[1].strip()

    # Convert operators
    right = right.replace("^2", " squared")
    right = right.replace("^3", " cubed")
    right = right.replace("^", " to the power of ")
    right = right.replace("*", " times ")
    right = right.replace("/", " divided by ")
    right = right.replace("+", " plus ")
    right = right.replace("-", " minus ")

    return f"{left} equals {right}"


def extract_formula_semantics(formula: str) -> dict[str, any]:
    """
    Extract semantic information from formula.

    Args:
        formula: Formula string

    Returns:
        Dict with semantic information
    """
    semantics = {"variables": [], "operators": [], "constants": [], "functions": []}

    # Extract variables (single letters)
    variables = re.findall(r"\b[a-zA-Z]\b", formula)
    semantics["variables"] = list(set(variables))

    # Extract operators
    operators = re.findall(r"[+\-*/^=]", formula)
    semantics["operators"] = list(set(operators))

    # Extract numbers (constants)
    constants = re.findall(r"\b\d+\.?\d*\b", formula)
    semantics["constants"] = list(set(constants))

    # Extract functions (e.g., sin, cos, log)
    functions = re.findall(r"\b(sin|cos|tan|log|ln|exp|sqrt)\b", formula, re.IGNORECASE)
    semantics["functions"] = list(set(functions))

    return semantics


def enrich_text_with_formulas(text: str) -> str:
    """
    Enrich text by adding natural language descriptions of formulas.

    Args:
        text: Input text with formulas

    Returns:
        Text with formula descriptions added
    """
    formulas = detect_formula(text)

    if not formulas:
        return text

    enriched = text

    # Sort by position (reverse) to avoid offset issues
    formulas.sort(key=lambda x: x["position"], reverse=True)

    for formula_info in formulas:
        formula = formula_info["formula"]
        formula_type = formula_info["type"]
        raw = formula_info["raw"]

        # Generate description
        description = formula_to_text(formula, formula_type)

        # Add description after formula
        enriched = enriched.replace(raw, f"{raw} [{description}]", 1)

    return enriched


def extract_formula_relationships(text: str) -> list[dict[str, str]]:
    """
    Extract relationships expressed in formulas.

    Args:
        text: Text with formulas

    Returns:
        List of relationship dicts
    """
    formulas = detect_formula(text)
    relationships = []

    for formula_info in formulas:
        formula = formula_info["formula"]

        # Parse equation relationships
        if "=" in formula:
            parts = formula.split("=")
            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()

                # Extract variables
                left_vars = re.findall(r"\b[a-zA-Z]\b", left)
                right_vars = re.findall(r"\b[a-zA-Z]\b", right)

                # Create relationships
                for lv in left_vars:
                    for rv in right_vars:
                        relationships.append({"head": lv, "relation": "EQUALS", "tail": rv, "formula": formula})

                # Check for proportionality
                if "*" in right or "/" in right:
                    for rv in right_vars:
                        relationships.append({"head": left, "relation": "DEPENDS_ON", "tail": rv, "formula": formula})

    return relationships
