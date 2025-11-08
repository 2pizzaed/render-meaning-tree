def g(_):  # id10 (function_definition) / id9 (function_declaration)
    return 'gone'  # id7 (return_statement) -> expr id6

if g('go'):  # id31 (if_statement) -> call id13 (arg id12)
    a = 'b'  # id17 (variable_declaration) -> init id15
    d = 'pass'  # id22 (variable_declaration) -> init id20
    e = 'step == (0,0,0)'  # id27 (variable_declaration) -> init id25

