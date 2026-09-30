20 episodios con semilla por modo, 400 ticks, 4 robots, pesos `W_linear_best.npy`, epsilon 0.05.

| Modo | Entregas válidas / episodio | Ticks por entrega | Recogidas fantasma | Misiones duplicadas | Esperas forzadas por conflicto | Colisiones (misma celda) | Eventos de atasco | Tiempo ocioso (%) | Re-subastas | vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 18.4 ± 2.5 | 24.4 | 1.7 | 6.4 | 0.3 | 0.3 | 0.0 | 20.2 | 0.0 | - |
| greedy+blackboard | 18.7 ± 2.4 | 23.8 | 1.8 | 6.5 | 0.0 | 0.0 | 0.0 | 20.0 | 0.0 | +1% |
| auction+legacy | 38.0 ± 2.6 | 10.8 | 0.0 | 0.0 | 0.5 | 0.5 | 0.0 | 2.4 | 2.6 | +106% |
| auction | 37.9 ± 2.7 | 10.8 | 0.0 | 0.0 | 0.1 | 0.0 | 0.0 | 2.4 | 2.8 | +105% |
