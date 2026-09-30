"""Registers the entities, permissions and modules of the product before the engine opens the data.

The product's own registration (platform and activity modules) is added here in later phases. SBO_ENTITY_MODULES
(comma separated module names, each with a register() function) lets tests and tools add their own test domain."""
import importlib
import os


def register_domains():
    """SBO_ENTITY_MODULES replaces the product's own domain (used by the engine tests); without it the product is registered."""
    names = [n.strip() for n in os.environ.get('SBO_ENTITY_MODULES', '').split(',') if n.strip()]
    if not names:
        import business  # server/business: the product's entities and permissions
        business.register()
    for name in names:
        importlib.import_module(name).register()
