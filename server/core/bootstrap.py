"""Registers the entities, permissions and modules of the product before the engine opens the data.

The product's own registration (platform and activity modules) is added here in later phases. SBO_ENTITY_MODULES
(comma separated module names, each with a register() function) lets tests and tools add their own test domain."""
import importlib
import os


def register_domains():
    for name in filter(None, os.environ.get('SBO_ENTITY_MODULES', '').split(',')):
        importlib.import_module(name.strip()).register()
