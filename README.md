# dmf

An instance of a dynamic monotone framework for type analysis for Python.

## The principles of dmf

1. Construct a control flow graph *G*
2. Extract flows *F* from *G*
3. Construct a points-to analysis framework *P*
4. Construct a monotone framework *MF* based on *P*
5. Compute type information *T* by maximal fixed point algorithm

## Supported language constructs
- [] Module
- [] FunctionDef
- [] AsyncFunctionDef
- [] ClassDef
- [] Return
- [] Delete
- [] Assign
- [] AugAssign
- [] AnnAssign
- [] For
- [] AsyncFor
- [] While
- [] If
- [] with
- [] AsyncWith
- [] Raise
- [] Try
- [] Assert
- [] Import
- [] ImportFrom
- [] Global
- [] Nonlocal
- [] Expr
- [] Pass
- [] Break
- [] Continue

- [x] BoolOp
- [x] BinOp
- [x] UnaryOp
- [x] Lambda
- [x] Dict
- [x] Set
- [x] ListComp
- [x] SetComp
- [x] DictComp
- [] GeneratorExp
- [] Await
- [] Yield
- [] YieldFrom
- [] Compare
- [] Call
- [x] Num
- [x] Str
- [x] FormattedValue
- [x] JoinedStr
- [x] Bytes
- [x] NameConstant
- [] Ellipsis
- [] Constant
- [] Attribute
- [] Subscript
- [] Starred
- [x] Name
- [x] List
- [x] Tuple
