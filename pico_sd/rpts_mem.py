"""Free-RAM reporter. At the on-screen REPL:

    import sys; sys.path.insert(0,'/sd'); import rpts_mem

Prints the free heap after a full collect — useful for diagnosing
memory-allocation errors. Report the 'free after collect' number.
"""
import gc

gc.collect()
try:
    free = gc.mem_free()
    alloc = gc.mem_alloc()
    print("free after collect :", free, "bytes")
    print("allocated          :", alloc, "bytes")
    print("total heap         :", free + alloc, "bytes")
except AttributeError:
    print("gc.mem_free() unavailable on this build")
