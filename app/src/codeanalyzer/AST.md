# Comparing Query-Based vs. Tree Walking Approaches

After implementing both approaches, I can now provide a more informed opinion on their relative merits for your Java parsing use case.

## Analysis

### Maintainability
The query-based approach initially appeared to offer better maintainability through separation of concerns. However, in practice:

- **Tree Walking Wins**: The query-based implementation requires extensive post-processing logic to rebuild relationships between nodes, which actually introduces more complexity than the direct traversal approach.
- **Context Management**: In the tree walking approach, maintaining context (like "this is a field in this class") is natural. With queries, reconstructing these relationships requires complex filtering code.
- **Debugging**: The tree walking code makes it more obvious where and why parsing might fail, as there's a direct mapping between the code structure and the AST structure.

### Performance
- **Tree Walking Wins** (for your specific use case): While theoretically, the query should allow one pass through the tree, the extensive post-processing required to sort and relate the query results likely negates most of that advantage.
- **Memory Usage**: The query-based approach requires storing intermediate collections of all matched nodes, which could be memory-intensive for large files.

### Code Complexity
- **Tree Walking Wins**: Despite more lines of traversal code, each method in the original approach has a clear, focused responsibility.
- **Relationship Complexity**: The query approach required complex helper methods like `_is_sibling_or_modifier_child` and numerous list comprehensions to filter query results.

### Future Evolution
- **It Depends**: For simple syntax changes, the query approach excels as you'd just update the query pattern. For deeper structural changes or new analyses, both approaches would need significant updates.

## Evidence from the Implementation

Looking at the code demonstrates why tree walking is more maintainable in this case:

1. **Relationship Tracking**: Consider this query processing code:
   ```python
   annotation_nodes = [n for n, c in query_captures if c == "annotation" and 
                       self._is_sibling_or_modifier_child(n, node)]
   ```
   
   Compared to the explicit navigation in the tree walking approach:
   ```python
   modifiers_node = node.child_by_field_name("modifiers")
   if modifiers_node:
       for child in modifiers_node.children:
           # Process annotations directly
   ```

2. **Code Volume**: The query-based implementation actually required more code, even with a single query, because relationship rebuilding is verbose.

3. **Helper Method Proliferation**: The query approach needed extra helper methods like `_is_descendant`, `_get_parent`, etc., which were implicit in the tree walking approach.

## Conclusion

For your specific use case of deeply analyzing Java code structure, **the tree walking approach is superior** in terms of maintainability, readability, and likely performance.

The query-based approach shines when:
- You're searching for specific patterns without needing to build comprehensive models
- The language has simple rules for relating elements
- You need to perform targeted, isolated analyses rather than full parsing

For comprehensive Java parsing with complex relationships between classes, methods, annotations, etc., the direct tree walking approach better matches the mental model of the code structure and leads to more maintainable code.

Your intuition was actually correct - walking the tree directly for this particular analysis task provides better clarity and maintainability, especially given the complex interrelationships in Java code.

## Example Multiple Query Approach

To implement your parser with tree-sitter queries instead of direct node walking, you'd use a more declarative approach where the queries define what to extract rather than navigating the AST manually. Here's how to approach this:

## Query-Based Implementation

First, define your queries at initialization:

```python
def __init__(self):
    self.parser = get_parser("java")
    self.java_language = get_language("java")
    
    # Define queries for different elements
    self.class_query = self.java_language.query("""
        (class_declaration
          name: (identifier) @name.definition.class) @definition.class
        (interface_declaration
          name: (identifier) @name.definition.interface) @definition.interface
    """)
    
    self.package_query = self.java_language.query("""
        (package_declaration
          name: (scoped_identifier) @package)
    """)
    
    self.import_query = self.java_language.query("""
        (import_declaration
          ["static" "import"] @import.modifiers
          name: (scoped_identifier) @import.name
          ["*"] @import.wildcard?)
    """)
    
    self.annotation_query = self.java_language.query("""
        (annotation
          name: (identifier) @annotation.name
          arguments: (annotation_argument_list)? @annotation.args)
        (marker_annotation 
          name: (identifier) @marker_annotation.name)
    """)
    
    self.field_query = self.java_language.query("""
        (field_declaration
          (modifiers)? @field.modifiers
          type: (_) @field.type
          declarator: (variable_declarator
            name: (identifier) @field.name
            value: (_)? @field.value))
    """)
    
    self.method_query = self.java_language.query("""
        (method_declaration
          (modifiers)? @method.modifiers
          type: (_) @method.return_type
          name: (identifier) @method.name
          parameters: (formal_parameters) @method.parameters
          body: (block)? @method.body) @method
    """)
    
    self.method_call_query = self.java_language.query("""
        (method_invocation
          object: (identifier) @call.object
          name: (identifier) @call.method
          arguments: (argument_list) @call.args)
    """)
    
    self.parameter_query = self.java_language.query("""
        (formal_parameter
          (modifiers)? @param.modifiers
          type: (_) @param.type
          name: (identifier) @param.name)
    """)
    
    self.rest_mapping_query = self.java_language.query("""
        (annotation
          name: (identifier) @mapping.type
          (#match? @mapping.type "(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)")
          arguments: (annotation_argument_list
            (element_value_pair
              key: (identifier) @mapping.key
              value: (_) @mapping.value)?)?)
    """)
```

Then you would execute these queries and process their results:

```python
def parse_java_file(self, file_path: str) -> JavaClass:
    with open(file_path, "rb") as f:
        source_code = f.read()
    
    tree = self.parser.parse(source_code)
    root_node = tree.root_node
    
    # Extract package
    package_matches = self.package_query.captures(root_node)
    package = self._extract_text(package_matches[0][0]) if package_matches else ""
    
    # Extract class/interface info
    class_matches = self.class_query.matches(root_node)
    if not class_matches:
        raise ValueError(f"No class or interface declaration found in {file_path}")
    
    # Process class info
    class_match = class_matches[0]
    class_node = None
    class_name = ""
    is_interface = False
    
    for capture in class_match.captures:
        if capture[1] == "name.definition.class":
            class_name = self._extract_text(capture[0])
            is_interface = False
        elif capture[1] == "name.definition.interface":
            class_name = self._extract_text(capture[0])
            is_interface = True
        elif capture[1] in ["definition.class", "definition.interface"]:
            class_node = capture[0]
    
    # Extract imports using query
    imports, import_statements = self._extract_imports(root_node)
    
    # Extract annotations for class
    class_annotations = self._extract_annotations(class_node)
    
    # Extract fields using query
    member_variables = self._extract_member_variables(class_node, source_code)
    
    # Extract methods using query
    methods = self._extract_methods(class_node, member_variables, source_code)
    
    # Determine class category
    category = infer_class_category(class_name, class_annotations)
    
    # Create class model
    return self._create_class_model(
        class_name=class_name, 
        package=package,
        class_annotations=class_annotations,
        category=category,
        # ... other parameters
    )
```

## Comparing the Two Approaches

Let's address your specific question about which approach is better:

### Query-Based Approach
**Pros:**
- More declarative and maintainable
- Separates pattern matching from processing logic
- Tree-sitter can potentially optimize query execution
- Multiple patterns can be combined in a single query
- Better for targeted extractions (like "find all method calls")

**Cons:**
- May require multiple separate queries for different components
- Can be harder to maintain context between query results
- Could be less efficient if you need to extract everything from the tree

### Direct Node Traversal Approach
**Pros:**
- Single pass through the tree (potentially more efficient for full-tree processing)
- Easier to maintain context between different elements
- More control over the traversal logic
- Can dynamically adjust extraction based on context

**Cons:**
- More imperative and harder to maintain
- Requires more boilerplate navigation code
- Less separation of concerns

## Best Approach for Your Case

Given your existing complex parser:

1. **For performance**: If you're analyzing entire codebases and need all the information you're currently extracting, your intuition is correct - a single traversal might be faster.

2. **For maintainability**: Queries are easier to understand and modify, especially for complex patterns like annotations.

3. **Hybrid solution**: You can use a hybrid approach where you:
   - Use queries for complex patterns (like annotations and method declarations)
   - Use direct traversal for connecting the results and building the model

Regarding your specific query example, it's a single query with multiple patterns. Each part (class_declaration, method_declaration, etc.) will match independently, so the query engine runs once but finds all these different nodes.

For your specific Java parsing needs, I'd recommend starting with queries for the complex patterns (like annotations, method declarations) and use direct traversal for the high-level structure, especially where context needs to be maintained between elements.

Would you like me to expand on the implementation details for any specific part of this conversion?

## Example Single Query Approach

Yes, we can create a single comprehensive query that captures all the relevant information at once. This approach can be more efficient as it processes the syntax tree only once rather than making multiple passes.

Here's how a comprehensive single query would look:

```python
def __init__(self):
    self.parser = get_parser("java")
    self.java_language = get_language("java")
    
    # Single comprehensive query for Java class analysis
    self.comprehensive_query = self.java_language.query("""
        ; Class and interface definitions
        (class_declaration
          name: (identifier) @class.name
          (modifiers) @class.modifiers?
          body: (class_body) @class.body
          superclass: (superclass
            (type_identifier) @class.superclass.name)? 
          interfaces: (interfaces
            (type_list) @class.interfaces)?) @class
        
        (interface_declaration 
          name: (identifier) @interface.name
          (modifiers) @interface.modifiers?
          body: (class_body) @interface.body) @interface
        
        ; Package declaration
        (package_declaration
          name: (scoped_identifier) @package.name) @package
        
        ; Import statements
        (import_declaration
          ["static" "import"] @import.modifiers?
          name: (scoped_identifier) @import.name
          ["*"] @import.wildcard?) @import
        
        ; Annotations (both full and marker)
        (annotation
          name: (identifier) @annotation.name
          arguments: (annotation_argument_list)? @annotation.args) @annotation
        
        (marker_annotation 
          name: (identifier) @marker.name) @marker_annotation
        
        ; Annotation values
        (element_value_pair
          key: (identifier) @annotation.arg.key
          value: (_) @annotation.arg.value) @annotation.arg
        
        ; Fields/member variables
        (field_declaration
          (modifiers)? @field.modifiers
          type: (_) @field.type
          declarator: (variable_declarator
            name: (identifier) @field.name
            value: (_)? @field.value)) @field
        
        ; Methods
        (method_declaration
          (modifiers)? @method.modifiers
          type: (_) @method.return_type
          name: (identifier) @method.name
          parameters: (formal_parameters) @method.parameters
          (throws)? @method.throws?
          body: (block)? @method.body) @method
        
        ; Method parameters
        (formal_parameter
          (modifiers)? @param.modifiers
          type: (_) @param.type
          name: (identifier) @param.name) @param
        
        ; Method calls
        (method_invocation
          object: (identifier) @call.object
          name: (identifier) @call.method
          arguments: (argument_list) @call.args) @method_call
        
        ; Literals and constants
        (string_literal) @string_literal
        (field_access) @field_access
        (identifier) @identifier
    """)
```

Then, in your parsing function, you would execute this single query and organize the results:

```python
def parse_java_file(self, file_path: str) -> JavaClass:
    with open(file_path, "rb") as f:
        source_code = f.read()
    
    tree = self.parser.parse(source_code)
    root_node = tree.root_node
    
    # Execute the comprehensive query
    matches = self.comprehensive_query.captures(root_node)
    
    # Create dictionaries to organize results by node type
    class_info = {}
    package_info = {}
    imports = []
    annotations = {}
    fields = []
    methods = []
    method_calls = {}
    
    # Process all query matches
    for node, capture_name in matches:
        node_text = self._extract_text(node)
        
        # Organize by capture group
        if capture_name.startswith("class."):
            class_info[capture_name] = (node, node_text)
        elif capture_name.startswith("interface."):
            class_info[capture_name] = (node, node_text) 
            class_info["is_interface"] = True
        elif capture_name.startswith("package."):
            package_info[capture_name] = (node, node_text)
        elif capture_name.startswith("import."):
            if capture_name == "import":
                imports.append(node)
        elif capture_name.startswith("annotation.") or capture_name.startswith("marker."):
            # Use the node id as key to group related annotation parts
            node_id = id(node)
            if node_id not in annotations:
                annotations[node_id] = {"node": node, "parts": {}}
            annotations[node_id]["parts"][capture_name] = (node, node_text)
        elif capture_name.startswith("field."):
            if capture_name == "field":
                fields.append(node)
        elif capture_name.startswith("method."):
            if capture_name == "method":
                methods.append(node)
        elif capture_name.startswith("call."):
            # Group method calls by their parent method
            parent_method = self._find_parent_method(node, methods)
            if parent_method:
                method_id = id(parent_method)
                if method_id not in method_calls:
                    method_calls[method_id] = []
                method_calls[method_id].append((capture_name, node, node_text))
    
    # Now process these organized results to build your model
    # This replaces multiple separate extraction methods
    
    # Extract class name and type
    class_name = class_info.get("class.name", (None, ""))[1]
    is_interface = class_info.get("is_interface", False)
    
    # Extract package
    package = package_info.get("package.name", (None, ""))[1]
    
    # Process imports, annotations, fields, methods, etc.
    # ...
    
    # Return the constructed JavaClass object
    # ...
```

## Benefits of this Approach

1. **Single Tree Traversal:** Tree-sitter does the work of finding all patterns in one pass through the syntax tree.

2. **Contextual Relationships:** You can better maintain relationships between nodes (e.g., which annotations belong to which methods or fields).

3. **Comprehensive Capture:** You get all relevant nodes in a single operation, making it easier to establish parent-child relationships.

4. **Better Performance:** Especially for large files, as you only parse and query the tree once.

The key challenge with this approach is organizing the results - you need a post-processing phase to group related nodes together (e.g., connecting method parameters to their parent methods). But for many use cases, this is more than offset by the efficiency gain of a single query.

Here's a complete implementation of `parse_java_file` using a single comprehensive query:

```python
def parse_java_file(self, file_path: str) -> Union[JavaClass, RestControllerClass, ServiceClass]:
    """
    Parse a Java file using a single comprehensive query and extract class information.

    Args:
        file_path: Path to the Java file

    Returns:
        A JavaClass or subclass instance representing the parsed Java file
    """
    with open(file_path, "rb") as f:
        source_code = f.read()

    tree = self.parser.parse(source_code)
    root_node = tree.root_node

    # Execute the comprehensive query
    query_captures = self.comprehensive_query.captures(root_node)

    # Track nodes by their ID to maintain relationships
    nodes_by_id = {}
    nodes_by_type = {
        "class": [],
        "interface": [],
        "package": [],
        "import": [],
        "annotation": [],
        "marker_annotation": [],
        "field": [],
        "method": [],
        "method_call": [],
        "param": [],
    }

    # First pass: Catalog all nodes by type and ID
    for node, capture_name in query_captures:
        node_id = id(node)
        if node_id not in nodes_by_id:
            nodes_by_id[node_id] = {"node": node, "captures": {}}
        
        nodes_by_id[node_id]["captures"][capture_name] = node
        
        # Also track by primary node types
        if capture_name in nodes_by_type:
            nodes_by_type[capture_name].append(node)

    # Extract package name
    package = ""
    if nodes_by_type["package"]:
        package_node = nodes_by_type["package"][0]
        name_captures = [n for n, c in query_captures if c == "package.name" and self._get_parent(n) == package_node]
        if name_captures:
            package = self._extract_text(name_captures[0])

    # Extract imports
    imports = []
    import_statements = []
    for import_node in nodes_by_type["import"]:
        # Find related captures for this import node
        is_static = False
        is_wildcard = False
        import_name = ""
        
        for node, capture_name in query_captures:
            if self._get_parent(node) == import_node:
                if capture_name == "import.name":
                    import_name = self._extract_text(node)
                elif capture_name == "import.wildcard":
                    is_wildcard = True
                elif capture_name == "import.modifiers" and self._extract_text(node) == "static":
                    is_static = True
        
        if import_name:
            if is_wildcard and not import_name.endswith(".*"):
                import_name = f"{import_name}.*"
            
            imports.append(
                ImportDefinition(
                    fully_qualified_name=import_name,
                    is_static=is_static,
                    is_wildcard=is_wildcard
                )
            )
            import_statements.append(import_name)

    # Find the class or interface declaration
    is_interface = False
    class_node = None
    class_name = ""
    
    if nodes_by_type["class"]:
        class_node = nodes_by_type["class"][0]
        class_name_nodes = [n for n, c in query_captures if c == "class.name" and self._get_parent(n).id == class_node.id]
        if class_name_nodes:
            class_name = self._extract_text(class_name_nodes[0])
    elif nodes_by_type["interface"]:
        class_node = nodes_by_type["interface"][0]
        is_interface = True
        class_name_nodes = [n for n, c in query_captures if c == "interface.name" and self._get_parent(n).id == class_node.id]
        if class_name_nodes:
            class_name = self._extract_text(class_name_nodes[0])
    
    if not class_node:
        raise ValueError(f"No class or interface declaration found in {file_path}")

    # Extract class annotations
    class_annotations = self._extract_annotations_for_node(class_node, query_captures)

    # Determine abstraction type and class category
    from .models import AbstractionType
    abstraction_type = AbstractionType.INTERFACE if is_interface else None
    
    # If it's a class, check if it's abstract
    if not is_interface:
        modifiers_nodes = [n for n, c in query_captures if c == "class.modifiers" and self._get_parent(n).id == class_node.id]
        if modifiers_nodes:
            modifiers_text = self._extract_text(modifiers_nodes[0])
            if "abstract" in modifiers_text:
                abstraction_type = AbstractionType.ABSTRACT
    
    # Infer class category from annotations and name
    category = infer_class_category(class_name, class_annotations)

    # Extract class body node for member variables and methods
    body_node = None
    body_nodes = [n for n, c in query_captures if (c == "class.body" or c == "interface.body") and self._get_parent(n).id == class_node.id]
    if body_nodes:
        body_node = body_nodes[0]

    # Extract implements interfaces
    implements = []
    if not is_interface:
        interface_nodes = [n for n, c in query_captures if c == "class.interfaces" and self._get_parent(n).id == class_node.id]
        if interface_nodes:
            interface_text = self._extract_text(interface_nodes[0])
            # Parse the interface text to extract individual interface names
            # This is simplified - you might need more robust parsing
            interface_names = [i.strip() for i in interface_text.split(",")]
            implements.extend(interface_names)

    # Extract member variables
    member_variables = []
    for field_node in nodes_by_type["field"]:
        if body_node and self._is_descendant(field_node, body_node):
            # For each field, extract name, type, annotations, modifiers
            field_name = ""
            field_type = ""
            field_value = None
            
            # Get field name
            name_nodes = [n for n, c in query_captures if c == "field.name" and self._is_descendant(n, field_node)]
            if name_nodes:
                field_name = self._extract_text(name_nodes[0])
            
            # Get field type
            type_nodes = [n for n, c in query_captures if c == "field.type" and self._is_descendant(n, field_node)]
            if type_nodes:
                field_type = self._extract_text(type_nodes[0])
            
            # Get field value if any
            value_nodes = [n for n, c in query_captures if c == "field.value" and self._is_descendant(n, field_node)]
            if value_nodes:
                field_value = self._extract_text(value_nodes[0])
            
            # Get annotations and modifiers
            annotations = self._extract_annotations_for_node(field_node, query_captures)
            modifiers = self._extract_modifiers_for_node(field_node, query_captures, "field.modifiers")
            
            # Determine if it's a constant (static final)
            is_constant = "static" in modifiers and "final" in modifiers
            
            # Determine category and create appropriate MemberVariable
            category = self._determine_member_variable_category(field_type)
            
            if category == MemberVariableCategory.CLASS_REFERENCE:
                # Check for autowired and qualifier annotations
                is_autowired = any(a.name == "Autowired" for a in annotations)
                qualifier = None
                for anno in annotations:
                    if anno.name == "Qualifier":
                        qualifier = anno.value
                
                # Create ClassReferenceMemberVariable
                from .models import ElementType, ReferenceLocation, UnresolvedAutowire, UnresolvedType
                
                unresolved_type = None
                if category == MemberVariableCategory.CLASS_REFERENCE:
                    unresolved_type = UnresolvedType(
                        raw_value=field_type,
                        location=ReferenceLocation(
                            class_name=class_name,
                            element_type=ElementType.FIELD_DECLARATION,
                            element_name=field_name,
                        ),
                        is_interface=False,
                        is_generic="<" in field_type and ">" in field_type,
                    )
                
                unresolved_autowire = None
                if is_autowired and category == MemberVariableCategory.CLASS_REFERENCE:
                    unresolved_autowire = UnresolvedAutowire(
                        raw_value=field_type,
                        location=ReferenceLocation(
                            class_name=class_name,
                            element_type=ElementType.FIELD_DECLARATION,
                            element_name=field_name,
                        ),
                        interface_type=field_type,
                        qualifier=qualifier,
                    )
                
                referenced_category = self._determine_referenced_class_category(field_type)
                
                member_variables.append(
                    ClassReferenceMemberVariable(
                        name=field_name,
                        type=field_type,
                        category=category,
                        annotations=annotations,
                        modifiers=modifiers,
                        is_autowired=is_autowired,
                        qualifier=qualifier,
                        referenced_class_category=referenced_category,
                        unresolved_type=unresolved_type,
                        unresolved_autowire=unresolved_autowire,
                    )
                )
            else:
                # Create regular MemberVariable
                member_variables.append(
                    MemberVariable(
                        name=field_name,
                        type=field_type,
                        category=category,
                        annotations=annotations,
                        modifiers=modifiers,
                    )
                )
            
            # If it's a constant, add to the constants dictionary
            if is_constant and field_value and field_value.startswith('"') and field_value.endswith('"'):
                constants[field_name] = field_value[1:-1]  # Remove quotes

    # Extract constants (static final fields)
    constants = {}
    for field_node in nodes_by_type["field"]:
        if body_node and self._is_descendant(field_node, body_node):
            modifiers = self._extract_modifiers_for_node(field_node, query_captures, "field.modifiers")
            
            if "static" in modifiers and "final" in modifiers:
                name_nodes = [n for n, c in query_captures if c == "field.name" and self._is_descendant(n, field_node)]
                value_nodes = [n for n, c in query_captures if c == "field.value" and self._is_descendant(n, field_node)]
                
                if name_nodes and value_nodes:
                    name = self._extract_text(name_nodes[0])
                    value = self._extract_text(value_nodes[0])
                    
                    # If it's a string literal, remove the quotes
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                        constants[name] = value

    # Extract methods
    methods = []
    for method_node in nodes_by_type["method"]:
        if body_node and self._is_descendant(method_node, body_node):
            method_name = ""
            return_type = ""
            
            # Get method name and return type
            name_nodes = [n for n, c in query_captures if c == "method.name" and self._is_descendant(n, method_node)]
            type_nodes = [n for n, c in query_captures if c == "method.return_type" and self._is_descendant(n, method_node)]
            
            if name_nodes:
                method_name = self._extract_text(name_nodes[0])
            if type_nodes:
                return_type = self._extract_text(type_nodes[0])
            
            # Get annotations and modifiers
            annotations = self._extract_annotations_for_node(method_node, query_captures)
            modifiers = self._extract_modifiers_for_node(method_node, query_captures, "method.modifiers")
            
            # Extract parameters
            parameters = []
            param_nodes = [n for n, c in query_captures if c == "method.parameters" and self._is_descendant(n, method_node)]
            
            if param_nodes:
                formal_parameters = [n for n, c in query_captures if c == "param" and self._is_descendant(n, param_nodes[0])]
                
                for param_node in formal_parameters:
                    param_name = ""
                    param_type = ""
                    
                    name_nodes = [n for n, c in query_captures if c == "param.name" and self._is_descendant(n, param_node)]
                    type_nodes = [n for n, c in query_captures if c == "param.type" and self._is_descendant(n, param_node)]
                    
                    if name_nodes:
                        param_name = self._extract_text(name_nodes[0])
                    if type_nodes:
                        param_type = self._extract_text(type_nodes[0])
                    
                    param_annotations = self._extract_annotations_for_node(param_node, query_captures)
                    
                    parameters.append(
                        Parameter(
                            name=param_name,
                            type=param_type,
                            annotations=param_annotations
                        )
                    )
            
            # Extract exceptions
            exceptions = []
            throws_nodes = [n for n, c in query_captures if c == "method.throws" and self._is_descendant(n, method_node)]
            
            if throws_nodes:
                # Extract exception types from throws clause
                # This is simplified - you'll need more parsing to extract individual exception types
                throws_text = self._extract_text(throws_nodes[0])
                exception_types = [e.strip() for e in throws_text.replace("throws", "").split(",")]
                exceptions.extend([e for e in exception_types if e])
            
            # Extract method calls
            method_calls = []
            body_nodes = [n for n, c in query_captures if c == "method.body" and self._is_descendant(n, method_node)]
            
            if body_nodes:
                body_node = body_nodes[0]
                call_nodes = [n for n, c in query_captures if c == "method_call" and self._is_descendant(n, body_node)]
                
                for call_node in call_nodes:
                    object_nodes = [n for n, c in query_captures if c == "call.object" and self._is_descendant(n, call_node)]
                    method_nodes = [n for n, c in query_captures if c == "call.method" and self._is_descendant(n, call_node)]
                    args_nodes = [n for n, c in query_captures if c == "call.args" and self._is_descendant(n, call_node)]
                    
                    if object_nodes and method_nodes:
                        service_name = self._extract_text(object_nodes[0])
                        method_name = self._extract_text(method_nodes[0])
                        
                        # Find the service variable
                        service_var = None
                        for var in member_variables:
                            if isinstance(var, ClassReferenceMemberVariable) and var.name == service_name:
                                service_var = var
                                break
                        
                        if service_var:
                            arg_count = 0
                            if args_nodes:
                                args_text = self._extract_text(args_nodes[0])
                                arg_count = 0 if not args_text.strip() else len(args_text.split(","))
                            
                            method_calls.append(
                                MethodCallInfo(
                                    service_name=service_name,
                                    method_name=method_name,
                                    service_type=service_var.type,
                                    source_variable=service_var,
                                    arg_count=arg_count
                                )
                            )
            
            # Determine if this is a REST endpoint
            path_mappings = {}
            rest_mapping_types = {
                "GetMapping": "GET",
                "PostMapping": "POST",
                "PutMapping": "PUT",
                "DeleteMapping": "DELETE",
                "PatchMapping": "PATCH",
                "RequestMapping": "GET"  # Default method
            }
            
            for annotation in annotations:
                if annotation.name in rest_mapping_types:
                    http_method = rest_mapping_types[annotation.name]
                    
                    # For RequestMapping, check method attribute
                    if annotation.name == "RequestMapping" and "method" in annotation.values:
                        method_value = annotation.values["method"]
                        # Extract HTTP method from RequestMethod enum constants
                        method_mapping = {
                            "RequestMethod.GET": "GET",
                            "RequestMethod.POST": "POST",
                            "RequestMethod.PUT": "PUT",
                            "RequestMethod.DELETE": "DELETE",
                            "RequestMethod.PATCH": "PATCH"
                        }
                        for method_const, method_name in method_mapping.items():
                            if method_const in method_value:
                                http_method = method_name
                                break
                    
                    # Get the path from the annotation
                    path = annotation.value or ""
                    path_mappings[http_method] = path
            
            # Create appropriate method object
            if path_mappings:
                endpoint = RestEndpoint(
                    name=method_name,
                    return_type=return_type,
                    parameters=parameters,
                    annotations=annotations,
                    exceptions=exceptions,
                    modifiers=modifiers,
                    method_calls=method_calls,
                    path_mappings=path_mappings
                )
                methods.append(endpoint)
            else:
                methods.append(
                    JavaMethod(
                        name=method_name,
                        return_type=return_type,
                        parameters=parameters,
                        annotations=annotations,
                        exceptions=exceptions,
                        modifiers=modifiers,
                        method_calls=method_calls
                    )
                )

    # File location info
    path = Path(file_path)
    filename = path.name
    absolute_path = str(path.absolute())
    
    try:
        relative_path = filename
        common_roots = ["src", "java", "main"]
        parts = path.parts
        for root in common_roots:
            if root in parts:
                idx = parts.index(root)
                relative_path = str(Path(*parts[idx + 1:]))
                break
    except Exception:
        relative_path = filename

    # Create the appropriate class model
    java_class = self._create_class_model(
        class_name=class_name,
        package=package,
        class_annotations=class_annotations,
        category=category,
        abstraction_type=abstraction_type,
        member_variables=member_variables,
        methods=methods,
        imports=imports,
        import_statements=import_statements,
        constants=constants,
        filename=filename,
        relative_path=relative_path,
        absolute_path=absolute_path,
        implements=implements
    )

    # Set parent references for methods that need them
    for method in java_class.methods:
        if isinstance(method, RestEndpoint):
            method._parent_class = java_class

    return java_class

# Helper methods for the parser
def _extract_text(self, node) -> str:
    """Extract text from a node"""
    return node.text.decode('utf-8') if node else ""

def _get_parent(self, node):
    """Get the parent of a node"""
    return node.parent

def _is_descendant(self, node, potential_ancestor) -> bool:
    """Check if node is a descendant of potential_ancestor"""
    current = node
    while current:
        if current.id == potential_ancestor.id:
            return True
        current = current.parent
    return False

def _extract_annotations_for_node(self, node, query_captures) -> List[Annotation]:
    """Extract annotations for a specific node"""
    annotations = []
    
    # Find all annotation nodes that precede the target node or are in its modifiers
    annotation_nodes = [n for n, c in query_captures if c == "annotation" and self._is_sibling_or_modifier_child(n, node)]
    marker_nodes = [n for n, c in query_captures if c == "marker_annotation" and self._is_sibling_or_modifier_child(n, node)]
    
    # Process regular annotations
    for anno_node in annotation_nodes:
        name_nodes = [n for n, c in query_captures if c == "annotation.name" and self._get_parent(n).id == anno_node.id]
        args_nodes = [n for n, c in query_captures if c == "annotation.args" and self._get_parent(n).id == anno_node.id]
        
        if name_nodes:
            name = self._extract_text(name_nodes[0])
            values = {}
            
            if args_nodes:
                # Extract argument key-value pairs
                arg_pairs = [n for n, c in query_captures if c == "annotation.arg" and self._is_descendant(n, args_nodes[0])]
                
                for arg_pair in arg_pairs:
                    key_nodes = [n for n, c in query_captures if c == "annotation.arg.key" and self._get_parent(n).id == arg_pair.id]
                    value_nodes = [n for n, c in query_captures if c == "annotation.arg.value" and self._get_parent(n).id == arg_pair.id]
                    
                    if key_nodes and value_nodes:
                        key = self._extract_text(key_nodes[0])
                        value = self._extract_text(value_nodes[0])
                        
                        # If value is a string literal, remove quotes
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        
                        values[key] = value
            
            annotations.append(Annotation(name=name, values=values))
    
    # Process marker annotations
    for marker_node in marker_nodes:
        name_nodes = [n for n, c in query_captures if c == "marker.name" and self._get_parent(n).id == marker_node.id]
        
        if name_nodes:
            name = self._extract_text(name_nodes[0])
            annotations.append(Annotation(name=name))
    
    return annotations

def _extract_modifiers_for_node(self, node, query_captures, modifiers_capture) -> List[str]:
    """Extract modifiers for a specific node"""
    modifiers = []
    
    modifiers_nodes = [n for n, c in query_captures if c == modifiers_capture and self._get_parent(n).id == node.id]
    
    if modifiers_nodes:
        modifiers_text = self._extract_text(modifiers_nodes[0])
        modifiers = [m for m in modifiers_text.split() if m]
    
    return modifiers

def _is_sibling_or_modifier_child(self, node, target_node) -> bool:
    """Check if node is a sibling of target_node or a child of target_node's modifiers"""
    # Check if node is a sibling that precedes target_node
    current = target_node
    while current.prev_sibling:
        current = current.prev_sibling
        if current.id == node.id:
            return True
    
    # Check if node is inside target_node's modifiers
    for child in target_node.children:
        if child.type == "modifiers":
            for modifier_child in child.children:
                if modifier_child.id == node.id:
                    return True
    
    return False
```

This implementation:

1. Uses a single comprehensive query to extract all Java elements
2. Processes the query results to build the Java class model
3. Maintains relationships between different nodes
4. Extracts annotations for classes, methods, and fields
5. Identifies REST endpoints based on Spring annotations
6. Detects service method calls within method bodies
7. Builds the appropriate class model based on the class category

The key difference from your original approach is that it uses a declarative query to find all elements of interest in one pass, then processes those results to build the model. This can be more efficient than traversing the tree multiple times.

Several helper methods are included to assist with processing the query results. These make it easier to find related nodes and extract their text content.
