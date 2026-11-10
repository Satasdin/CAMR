# Figures on syrup bottles

`volume_ml` in `clinic/prescriptions/labels.py` works out the millilitres printed on a bottle, and it gives figures like 7.3 ml. The syringes we hand out are only graduated every 0.5 ml, so nobody at home can draw up 7.3, and reception keeps taking calls about it.

Change `volume_ml` so that the figure can actually be drawn up on those syringes. The bottle must show that same figure.
