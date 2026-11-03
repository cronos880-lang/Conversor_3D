"""Frontera completa de un sólido, incluidas las paredes de cavidades."""


def frontera_completa(solido):
    shells=solido.Shells()
    if not shells:
        raise ValueError('El sólido no contiene una frontera medible.')
    if len(shells)==1:
        return shells[0]
    import cadquery as cq
    # Medir el volumen sólido daría distancia cero para puntos en material.
    # Medir solo el primer shell ignoraría todas las cavidades interiores.
    return cq.Compound.makeCompound(shells)
