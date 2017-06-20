from direct.showbase.ShowBase import ShowBase


class MainGame(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)


app = MainGame()
app.run()
