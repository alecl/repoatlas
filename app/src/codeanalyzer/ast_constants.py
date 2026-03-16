from enum import Enum, StrEnum


class NodeType(StrEnum):
    # Existing types
    CLASS_DECLARATION = "class_declaration"
    INTERFACE_DECLARATION = "interface_declaration"
    ENUM_DECLARATION = "enum_declaration"
    ENUM_BODY = "enum_body"
    ENUM_CONSTANT = "enum_constant"
    ENUM_BODY_DECLARATIONS = "enum_body_declarations"
    ARGUMENT_LIST = "argument_list"
    MODIFIERS = "modifiers"
    MARKER_ANNOTATION = "marker_annotation"
    ANNOTATION = "annotation"
    IMPORT_DECLARATION = "import_declaration"
    PACKAGE_DECLARATION = "package_declaration"
    SCOPED_IDENTIFIER = "scoped_identifier"
    IDENTIFIER = "identifier"
    ASTERISK = "asterisk"
    FIELD_DECLARATION = "field_declaration"
    VARIABLE_DECLARATOR = "variable_declarator"
    FORMAL_PARAMETER = "formal_parameter"
    THROWS = "throws"
    TYPE_IDENTIFIER = "type_identifier"
    SCOPED_TYPE_IDENTIFIER = "scoped_type_identifier"
    CLASS_BODY = "class_body"
    INTERFACE_BODY = "interface_body"
    METHOD_DECLARATION = "method_declaration"
    STRING_LITERAL = "string_literal"
    FIELD_ACCESS = "field_access"
    TRUE = "true"
    FALSE = "false"
    ELEMENT_VALUE_PAIR = "element_value_pair"
    ELEMENT_VALUE_ARRAY_INITIALIZER = "element_value_array_initializer"
    TYPE_LIST = "type_list"
    COMMENT = "comment"
    LINE_COMMENT = "line_comment"
    BLOCK_COMMENT = "block_comment"
    JAVADOC_COMMENT = "javadoc_comment"

    # Method call and invocation types
    METHOD_INVOCATION = "method_invocation"

    # Expression types
    BINARY_EXPRESSION = "binary_expression"
    TERNARY_EXPRESSION = "ternary_expression"
    ARRAY_ACCESS = "array_access"
    OBJECT_CREATION_EXPRESSION = "object_creation_expression"
    CAST_EXPRESSION = "cast_expression"
    PARENTHESIZED_EXPRESSION = "parenthesized_expression"
    ASSIGNMENT_EXPRESSION = "assignment_expression"

    # Literal types
    DECIMAL_INTEGER_LITERAL = "decimal_integer_literal"
    HEX_INTEGER_LITERAL = "hex_integer_literal"
    OCTAL_INTEGER_LITERAL = "octal_integer_literal"
    BINARY_INTEGER_LITERAL = "binary_integer_literal"
    DECIMAL_FLOATING_POINT_LITERAL = "decimal_floating_point_literal"
    HEX_FLOATING_POINT_LITERAL = "hex_floating_point_literal"
    CHARACTER_LITERAL = "character_literal"
    NULL_LITERAL = "null_literal"

    # Type declarations
    BOOLEAN_TYPE = "boolean_type"

    # Statement types
    ENHANCED_FOR_STATEMENT = "enhanced_for_statement"
    IF_STATEMENT = "if_statement"
    RETURN_STATEMENT = "return_statement"
    THROW_STATEMENT = "throw_statement"
    EXPRESSION_STATEMENT = "expression_statement"

    # Block and structure types
    BLOCK = "block"
    FORMAL_PARAMETERS = "formal_parameters"
    CONSTRUCTOR_DECLARATION = "constructor_declaration"
    CONSTRUCTOR_BODY = "constructor_body"

    # Punctuation and delimiter types
    OPEN_PAREN = "("
    CLOSE_PAREN = ")"
    COMMA = ","
    SEMICOLON = ";"
    DOT = "."
    EQUALS = "="
    COLON = ":"
    QUESTION_MARK = "?"
    PLUS = "+"

    # Keywords and special identifiers
    THIS = "this"
    STATIC = "static"


class FieldName(StrEnum):
    NAME = "name"
    ARGUMENTS = "arguments"
    TYPE = "type"
    BODY = "body"
    INTERFACES = "interfaces"
    PARAMETERS = "parameters"
    VALUE = "value"
    OBJECT = "object"
    FIELD = "field"
