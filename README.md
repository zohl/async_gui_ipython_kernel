# Async GUI IPython Kernel

This enables the IPython kernel to receive `Comm` events while waiting for cells.

Currently, the IPython kernel will only process one message at a time. Including Comm events that are naturally asynchronous. This means you are currently unable to await changes in your `ipywidgets`. If you do, the `await` statement will hang indefinitely.


Being able to wait on user input in Jupyter opens up possibilities for building interfaces. For example, in the GIF below, you can `await` on a GUI that takes a series of inputs. 


## Quickstart

``` bash
git clone ...
pip install ./async-gui-ipython-kernel
python -m async_gui_ipython_kernel install --user

```

Make sure to set your kernel to `Async GUI Python 3 (async_gui_ipython_kernel)`.

## Example

The following snippet prints a sequence of numbers, and each iteration requires the user to click the button to continue. "Vanilla" kernel would not respond on the clicks.


``` python
import asyncio
import ipywidgets as widgets

def wait_for_click(w):
    e = asyncio.Event()
    def handler(_):
        e.set()
        w.on_click(handler, remove = True)
    w.on_click(handler)
    return e.wait()

btn = widgets.Button(description = 'push')
display(btn)

for i in range(1, 1 + 3):
    print(i)
    print('press button to continue...')
    await wait_for_click(btn)

print('done')

```


## Disclaimer

This is just an untested hack that could be useful.
