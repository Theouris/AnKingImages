"""AnKing Images Anki add-on entry point."""

# Anki provides ``aqt`` before importing add-ons. Keeping this module inert in a
# regular Python process lets the pure CSV/tag helpers be tested independently.
try:
    import aqt  # noqa: F401
except ModuleNotFoundError as error:
    if error.name != "aqt":
        raise
else:
    from .anking_images.addon import register

    register()
