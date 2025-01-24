import { Injectable } from '@angular/core';

interface IpcRenderer {
  send(channel: string, ...args: unknown[]): void;
}

interface ElectronModule {
  ipcRenderer: IpcRenderer;
}

interface ElectronWindow extends Window {
  process?: {
    type?: string;
  };
  require?: (module: string) => ElectronModule;
}

@Injectable({
  providedIn: 'root'
})
export class ElectronService {
  isElectron = false;
  ipcRenderer: IpcRenderer | null = null;

  constructor() {
    const win = window as ElectronWindow;
    
    // Check if running in Electron
    if (win?.process?.type) {
      this.isElectron = true;
      
      // Load electron IPC if available
      if (win.require) {
        try {
          this.ipcRenderer = win.require('electron').ipcRenderer;
        } catch (error) {
          console.error('Error loading electron ipcRenderer:', error);
        }
      }
    }
  }
} 