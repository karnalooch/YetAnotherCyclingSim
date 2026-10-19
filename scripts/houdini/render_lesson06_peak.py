"""Measured height profiles, explicitly separate from UE screenshots."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06GeometryRemote'
d=np.load(p/'peak_window.npz');x,y=d['peak_xy'];xs=d['x'];zs=d['z']
b=d['before'];a=d['after'];delta=d['delta']
fig,axs=plt.subplots(1,2,figsize=(12,4.8))
axs[0].plot(xs,b[y],label='Przed pasem',color='#1976d2')
axs[0].plot(xs,a[y],label='Po pasie',color='#d84315')
axs[0].axvline(xs[x],color='black',ls=':')
axs[0].scatter([xs[x],xs[x]],[b[y,x],a[y,x]],color=['#1976d2','#d84315'])
axs[0].annotate('58,50 m',xy=(xs[x],b[y,x]),xytext=(12,-15),textcoords='offset points')
axs[0].annotate('171,32 m',xy=(xs[x],a[y,x]),xytext=(12,8),textcoords='offset points')
axs[0].set(xlabel='Houdini X [m]',ylabel='Wysokość [m]',title='Przekrój: Z = -1787,75 m')
axs[0].legend();axs[0].grid(alpha=.2)
im=axs[1].imshow(delta,extent=[xs[0],xs[-1],zs[-1],zs[0]],cmap='coolwarm',vmin=-113,vmax=113,aspect='equal')
axs[1].plot(xs[x],zs[y],'kx',ms=12,mew=2)
axs[1].axhline(-1769.75,color='black',ls='--',lw=1,label='Granica źródłowego Working')
axs[1].set(xlabel='Houdini X [m]',ylabel='Houdini Z [m]',title='Zmiana wysokości; × = maksimum +112,82 m')
axs[1].legend(fontsize=8);fig.colorbar(im,ax=axs[1],label='Po minus przed [m]')
fig.suptitle('Pomiar cache — przekrój i mapa zmian, nie zrzut UE')
fig.tight_layout();fig.savefig(p/'peak_profile.png',dpi=160)
