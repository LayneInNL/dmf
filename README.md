# dmf

An instance of a dynamic monotone framework for type analysis for Python.

## The principles of dmf

1. Construct a control flow graph *G*
2. Extract flows *F* from *G*
3. Construct a points-to analysis framework *P*
4. Construct a monotone framework *MF* based on *P*
5. Compute type information *T* by maximal fixed point algorithm