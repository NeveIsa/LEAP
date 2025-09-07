import numpy as np
import matplotlib.pyplot as plt


# df/dx = g(x,y)


def euler(fn, x0, y0, xmax, h=0.001):

    xs = [x0]
    ys = [y0]
    
    while xs[-1] <= xmax:
        m = fn(xs[-1],ys[-1]) #slope
        
        xnew = xs[-1] + h
        ynew  = ys[-1] + m * h

        xs.append(xnew)
        ys.append(ynew)

    return xs,ys


## initial point x0 = 0 , y0 = f(x0) = 1
## df/dx = e^x => f(x) = e^x
#def g(x,y): return np.exp(x)
#xs,ys = euler(g, x0=0, y0=1, h=0.1, xmax=100)
#plt.plot(xs[30:40],ys[30:40], label='num sol')
#plt.plot(xs[30:40],np.exp(np.array(xs[30:40])), label="true sol")
#plt.legend()
#plt.savefig("ok.png")


## initial point x0 = 0 , y0 = f(x0) = 1
## df/dx = 2xy => f(x) = e^(x**2)
def g(x,y): return 2*x*y
xs,ys = euler(g, x0=0, y0=1, xmax=10)
plt.plot(xs[int(3e3):int(4e3)],ys[int(3e3):int(4e3)], label='num sol')
plt.plot(xs[int(3e3):int(4e3)],np.exp(np.array(xs[int(3e3):int(4e3)])**2), label="true sol")
plt.legend()
plt.savefig("ok.png")


