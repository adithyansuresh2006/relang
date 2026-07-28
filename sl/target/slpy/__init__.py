from slpy.engine import SLEngine

def sl(cols, lines, arg=''):
    """
    arg 
      -r random flags
      -d add dance people
      -l add more locomotives (number of l = number of loco)
      -F Fly
      -c C51 locomotive
      -a add people crying for help
    """
    engine = SLEngine(cols, lines, arg)
    while True:
        frame = engine.step()
        if frame is not None:
            yield frame
        else:
            return None
