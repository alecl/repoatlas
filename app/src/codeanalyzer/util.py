import json
import re


def node_to_dict(node):
    """
    Naively dumps a tree-sitter node tree to a dictionary representation, including type, position, text, and children.

    Args:
        node: A tree-sitter Node object to be converted.

    Returns:
        dict: A dictionary containing the node's type, start and end positions, optional text snippet, and recursively its children.
    """
    # 1) Basic info
    d = {
        "type": node.type,
        "start_point": node.start_point,  # (row, col)
        "end_point": node.end_point,
    }

    # 2) Optionally include the snippet of source text
    text = node.text.decode("utf-8").strip()
    if text:
        d["text"] = text

    # 3) Recurse into children
    children = []
    for idx, child in enumerate(node.children):
        # recurse
        child_dict = node_to_dict(child)

        # *Correctly* ask for the field‐name by index
        field = node.field_name_for_child(idx)
        if field is not None:
            child_dict["field_name"] = field

        children.append(child_dict)

    if children:
        d["children"] = children

    return d


# pre-compile once at module load
_collapse_re = re.compile(r"(?:[ \t]*\n){2,}")


def collapse_blank_lines(text: str) -> str:
    # 1) normalize all line endings to '\n'
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 2) in one pass, collapse any run of ≥2 blank lines into exactly one
    return _collapse_re.sub("\n\n", text)


# older version less efficient
# def collapse_blank_lines2(text: str) -> str:
#     # Normalize all line endings to \n for consistent processing
#     normalized = text.replace('\r\n', '\n').replace('\r', '\n')
#     lines = normalized.split('\n')
#     output = []
#     blank = False
#     for line in lines:
#         if line.strip() == '':  # This is a blank line (even if it has spaces/tabs)
#             if not blank:
#                 output.append('')
#                 blank = True
#             # else: skip this blank line (it's not the first in a run)
#         else:
#             output.append(line)
#             blank = False
#     # Rejoin using \n (optionally restore \r\n if needed)
#     return '\n'.join(output)

# used to get a field name for children so you can
# then use node.child_by_field_name("field_name")
# for i, child in enumerate(decl_node.children):
#     field = decl_node.field_name_for_child(i)
#     print(child.type, field)
