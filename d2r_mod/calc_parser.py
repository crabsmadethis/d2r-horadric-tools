"""D2R calc expression tokenizer, parser, and evaluator.

Handles the formula language used in Skills.txt columns:
calc1-calc10, DmgSymPerCalc, EDmgSymPerCalc, passivecalc, aurastatcalc.

Expression syntax:
  - Arithmetic: + - * /
  - Comparisons: < > <= >=
  - Ternary: cond ? true_val : false_val
  - Functions: min(a, b), max(a, b)
  - Skill refs: skill('Skill Name'.blvl), skill('Skill Name'.lvl)
  - Variables: lvl, par1-par20, ln12/ln34/ln56/ln78, dm12/dm34/dm78, edmn
"""

from dataclasses import dataclass

# --- Token types ---
NUMBER = "NUMBER"
IDENT = "IDENT"
STRING = "STRING"
OP = "OP"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
COMMA = "COMMA"
DOT = "DOT"


@dataclass
class Token:
    type: str
    value: str


def tokenize(expr: str) -> list[Token]:
    """Tokenize a D2R calc expression."""
    expr = expr.strip().strip('"')
    tokens: list[Token] = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c.isspace():
            i += 1
        elif c.isdigit():
            j = i
            while j < len(expr) and (expr[j].isdigit() or expr[j] == '.'):
                j += 1
            tokens.append(Token(NUMBER, expr[i:j]))
            i = j
        elif c == "'":
            j = i + 1
            while j < len(expr) and expr[j] != "'":
                j += 1
            tokens.append(Token(STRING, expr[i + 1 : j]))
            i = j + 1
        elif c.isalpha() or c == '_':
            j = i
            while j < len(expr) and (expr[j].isalnum() or expr[j] == '_'):
                j += 1
            tokens.append(Token(IDENT, expr[i:j]))
            i = j
        elif c in '+-':
            if c == '-' and (not tokens or tokens[-1].type in (OP, LPAREN, COMMA)):
                j = i + 1
                while j < len(expr) and (expr[j].isdigit() or expr[j] == '.'):
                    j += 1
                if j > i + 1:
                    tokens.append(Token(NUMBER, expr[i:j]))
                    i = j
                else:
                    tokens.append(Token(OP, c))
                    i += 1
            else:
                tokens.append(Token(OP, c))
                i += 1
        elif c in '*/':
            tokens.append(Token(OP, c))
            i += 1
        elif c in '<>':
            if i + 1 < len(expr) and expr[i + 1] == '=':
                tokens.append(Token(OP, c + '='))
                i += 2
            else:
                tokens.append(Token(OP, c))
                i += 1
        elif c == '?':
            tokens.append(Token(OP, '?'))
            i += 1
        elif c == ':':
            tokens.append(Token(OP, ':'))
            i += 1
        elif c == '(':
            tokens.append(Token(LPAREN, '('))
            i += 1
        elif c == ')':
            tokens.append(Token(RPAREN, ')'))
            i += 1
        elif c == ',':
            tokens.append(Token(COMMA, ','))
            i += 1
        elif c == '.':
            tokens.append(Token(DOT, '.'))
            i += 1
        else:
            raise ValueError(f"Unexpected character: {c!r} at position {i} in {expr!r}")
    return tokens


# --- AST nodes ---

class ASTNode:
    pass


@dataclass
class NumberNode(ASTNode):
    value: float


@dataclass
class VarNode(ASTNode):
    name: str


@dataclass
class BinOpNode(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode


@dataclass
class UnaryNegNode(ASTNode):
    operand: ASTNode


@dataclass
class TernaryNode(ASTNode):
    cond: ASTNode
    true_val: ASTNode
    false_val: ASTNode


@dataclass
class FuncCallNode(ASTNode):
    name: str
    args: list[ASTNode]


@dataclass
class SkillRefNode(ASTNode):
    skill_name: str
    attr: str  # 'blvl' or 'lvl'


# --- Parser ---

class Parser:
    """Recursive descent parser for D2R calc expressions."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, token_type: str) -> Token:
        t = self.advance()
        if t.type != token_type:
            raise ValueError(f"Expected {token_type}, got {t.type} ({t.value!r})")
        return t

    def parse(self) -> ASTNode:
        result = self._ternary()
        if self.pos < len(self.tokens):
            raise ValueError(f"Unexpected token at pos {self.pos}: {self.tokens[self.pos]}")
        return result

    def _ternary(self) -> ASTNode:
        left = self._comparison()
        if self.peek() and self.peek().type == OP and self.peek().value == '?':
            self.advance()
            true_val = self._ternary()
            t = self.advance()
            if t.type != OP or t.value != ':':
                raise ValueError(f"Expected ':' in ternary, got {t}")
            false_val = self._ternary()
            return TernaryNode(left, true_val, false_val)
        return left

    def _comparison(self) -> ASTNode:
        left = self._additive()
        if self.peek() and self.peek().type == OP and self.peek().value in ('<', '>', '<=', '>='):
            op = self.advance().value
            right = self._additive()
            return BinOpNode(op, left, right)
        return left

    def _additive(self) -> ASTNode:
        left = self._multiplicative()
        while self.peek() and self.peek().type == OP and self.peek().value in ('+', '-'):
            op = self.advance().value
            right = self._multiplicative()
            left = BinOpNode(op, left, right)
        return left

    def _multiplicative(self) -> ASTNode:
        left = self._unary()
        while self.peek() and self.peek().type == OP and self.peek().value in ('*', '/'):
            op = self.advance().value
            right = self._unary()
            left = BinOpNode(op, left, right)
        return left

    def _unary(self) -> ASTNode:
        if self.peek() and self.peek().type == OP and self.peek().value == '-':
            self.advance()
            return UnaryNegNode(self._primary())
        return self._primary()

    def _primary(self) -> ASTNode:
        t = self.peek()
        if t is None:
            raise ValueError("Unexpected end of expression")

        if t.type == NUMBER:
            self.advance()
            return NumberNode(float(t.value))

        if t.type == LPAREN:
            self.advance()
            inner = self._ternary()
            self.expect(RPAREN)
            return inner

        if t.type == IDENT:
            name = self.advance().value
            if self.peek() and self.peek().type == LPAREN:
                if name == 'skill':
                    return self._skill_ref()
                return self._func_call(name)
            return VarNode(name)

        raise ValueError(f"Unexpected token: {t.type} ({t.value!r})")

    def _skill_ref(self) -> SkillRefNode:
        self.expect(LPAREN)
        name_tok = self.expect(STRING)
        self.expect(DOT)
        attr_tok = self.expect(IDENT)
        self.expect(RPAREN)
        return SkillRefNode(name_tok.value, attr_tok.value)

    def _func_call(self, name: str) -> FuncCallNode:
        self.expect(LPAREN)
        args = [self._ternary()]
        while self.peek() and self.peek().type == COMMA:
            self.advance()
            args.append(self._ternary())
        self.expect(RPAREN)
        return FuncCallNode(name, args)


# --- Evaluator ---

def evaluate(node: ASTNode, ctx: dict) -> float:
    """Evaluate an AST node.

    Context dict keys:
      lvl, par1-par20, ln12/ln34/ln56/ln78, dm12/dm34/dm78, edmn -> float
      skill_levels -> dict[str, int]  (skill name -> invested level)
    """
    if isinstance(node, NumberNode):
        return node.value
    if isinstance(node, VarNode):
        return float(ctx.get(node.name, 0))
    if isinstance(node, BinOpNode):
        left = evaluate(node.left, ctx)
        right = evaluate(node.right, ctx)
        if node.op == '+':
            return left + right
        if node.op == '-':
            return left - right
        if node.op == '*':
            return left * right
        if node.op == '/':
            return left / right if right != 0 else 0.0
        if node.op == '<':
            return 1.0 if left < right else 0.0
        if node.op == '>':
            return 1.0 if left > right else 0.0
        if node.op == '<=':
            return 1.0 if left <= right else 0.0
        if node.op == '>=':
            return 1.0 if left >= right else 0.0
    if isinstance(node, UnaryNegNode):
        return -evaluate(node.operand, ctx)
    if isinstance(node, TernaryNode):
        return evaluate(node.true_val, ctx) if evaluate(node.cond, ctx) else evaluate(node.false_val, ctx)
    if isinstance(node, FuncCallNode):
        args = [evaluate(a, ctx) for a in node.args]
        if node.name == 'min':
            return min(args)
        if node.name == 'max':
            return max(args)
        return 0.0
    if isinstance(node, SkillRefNode):
        return float(ctx.get('skill_levels', {}).get(node.skill_name, 0))
    raise ValueError(f"Unknown node: {type(node)}")


def eval_expr(expr: str, ctx: dict) -> float:
    """Parse and evaluate a D2R calc expression. Returns 0.0 for empty/blank."""
    if not expr or not expr.strip() or expr.strip().strip('"') == '':
        return 0.0
    tokens = tokenize(expr)
    if not tokens:
        return 0.0
    return evaluate(Parser(tokens).parse(), ctx)
