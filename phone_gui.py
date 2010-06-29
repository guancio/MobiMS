import appuifw
import e32

def exit_key_handler():
    app_lock.signal()

appuifw.app.menu = [(u"Exit", exit_key_handler)]

appuifw.app.title = u"MobiMS"
 
app_lock = e32.Ao_lock()

t = appuifw.Text()
# These and other similar values and combinations are valid:
t.style = appuifw.STYLE_BOLD
t.add(u"MobiMS\n")
t.add(u"\n")
t.add(u"by Guancio\n")

appuifw.app.body = t

appuifw.app.exit_key_handler = exit_key_handler
app_lock.wait()
