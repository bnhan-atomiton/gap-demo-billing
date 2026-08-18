"""CRUD routers, one module per table.

Deliberately empty of re-exports: `app/main.py` imports the modules and calls
`include_router` on each, so the list of what is mounted is in one place and a
router can be commented out without editing two files.
"""
