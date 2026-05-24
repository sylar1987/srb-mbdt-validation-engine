"""Formale Grammatik der DSL als Referenz.

Die tatsächliche Implementierung ist ein handgeschriebener Recursive-
Descent-Parser (siehe ``parser.py``). Dieses Modul dokumentiert die
Grammatik in EBNF-naher Form für Reviewer und für spätere Tools wie
einen Grammatik-Validator. Es enthält bewusst keinen ausführbaren Parser
zur Build-Zeit, um keine Lark/Antlr-Abhängigkeit einzuführen.
"""

GRAMMAR_EBNF = """
expression   = or_expr ;
or_expr      = and_expr , { "or" , and_expr } ;
and_expr     = membership , { "and" , membership } ;
membership   = comparison , { ( "in" | "not in" ) , comparison } ;
comparison   = additive , [ cmp_op , additive ] ;
cmp_op       = "=" | "==" | "!=" | "<>" | "<" | "<=" | ">" | ">=" ;
additive     = multiplicative , { ( "+" | "-" ) , multiplicative } ;
multiplicative = unary , { ( "*" | "/" ) , unary } ;
unary        = ( "not" | "-" | "+" ) , unary | primary ;
primary      = literal | reference | function_call | list_expr | "(" , expression , ")" ;
literal      = number | string | "true" | "false" | "null" ;
reference    = field_ref | template_ref | cross_ref ;
field_ref    = "c" , 4 * digit ;
template_ref = letter , digit , { digit } , [ "." , digit , digit ] ;
cross_ref    = template_ref , "." , field_ref ;
function_call = identifier , "(" , [ expression , { "," , expression } ] , ")" ;
list_expr    = "(" , expression , "," , expression , { "," , expression } , ")"
             | "[" , [ expression , { "," , expression } ] , "]" ;
"""
"""EBNF-nahe Referenzgrammatik der DSL (siehe parser.py für die Umsetzung)."""
