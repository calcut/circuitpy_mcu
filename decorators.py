def exception_decorator(func):
    """
    Can be used to decorate methods of a class which has a catch-all 
    handle_exception() function.
    Does a try/except on the method and throws any exceptions to the exception handler

    WARNING this doesn't really help, as it adds extra layers to the pystack, causing pystack exausted!
    """
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self.handle_exception(e)
    return wrapper