from async_gui_ipython_kernel import (
    AsyncGUIKernelApp,
    AsyncGUIKernel)


if __name__ == '__main__':
    AsyncGUIKernelApp.launch_instance(kernel_class = AsyncGUIKernel)
