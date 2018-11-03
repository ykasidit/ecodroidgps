from bbfreeze import Freezer

freezer = Freezer(distdir='dist')
freezer.addScript('*.py', gui_only=False)
freezer()
