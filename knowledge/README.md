# knowledge/ — conocimiento estructural

Datos del Knowledge Model v1. **Mantenidos a mano y versionados en git**, a diferencia de `data/current/` o `data/coverage.json`: su historial de cambios *es* información. Ver `engine/knowledge/README.md` para el modelo y las reglas.

```
entities/        quién o qué es cada cosa (identidad, aliases, estado)
concepts/        magnitudes económicas independientes del nombre de la métrica
relationships/   cómo se relacionan dos entidades, con fuente y vigencia
sources/         de dónde sale cada afirmación
pendiente/       CANDIDATO: declarado sin fuente. NO se carga y NO valida.
```

El seed A se extrajo una sola vez del propio repositorio y cada relación cita su origen por `fichero:línea`. A partir de ahí se mantiene a mano: esto no es un pipeline.

```bash
python3 engine/knowledge/consulta.py --validar
```
