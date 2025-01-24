import { Component, Input } from '@angular/core';
import { ElectronService } from '../core/services';

interface MetadataStatus {
  status: string;
  path?: string;
  error?: string;
}

interface MetadataItem {
  name: string;
  status: string;
  path?: string;
  error?: string;
}

interface FileItem {
  name: string;
  path: string;
}

interface Download {
  title: string;
  metadata?: {
    video?: {
      duration: string;
      view_count: number;
      like_count: number;
    };
    channel?: {
      title: string;
    };
    files?: {[key: string]: string};
  };
  metadata_status?: {[key: string]: MetadataStatus};
}

@Component({
  selector: 'app-completed-downloads',
  templateUrl: './completed-downloads.component.html',
  styleUrls: ['./completed-downloads.component.sass']
})
export class CompletedDownloadsComponent {
  @Input() downloads: Download[] = [];

  constructor(private electronService: ElectronService) {}

  getMetadataItems(metadata_status: {[key: string]: MetadataStatus}): MetadataItem[] {
    if (!metadata_status) return [];
    
    const displayNames: {[key: string]: string} = {
      'description': 'Description',
      'thumbnail': 'Thumbnail',
      'info_json': 'Metadata JSON',
      'subtitles': 'Subtitles',
      'transcript': 'Transcript'
    };

    return Object.entries(metadata_status).map(([key, value]) => ({
      name: displayNames[key] || key,
      status: value.status,
      path: value.path,
      error: value.error
    }));
  }

  getFiles(files: {[key: string]: string}): FileItem[] {
    if (!files) return [];

    const displayNames: {[key: string]: string} = {
      'audio': 'Audio File',
      'video': 'Video File',
      'thumbnail': 'Thumbnail',
      'description': 'Description',
      'info_json': 'Metadata JSON',
      'subtitles': 'Subtitles'
    };

    return Object.entries(files).map(([key, path]) => ({
      name: displayNames[key] || key,
      path
    }));
  }

  getStatusIcon(status: string): string {
    switch (status) {
      case 'completed':
        return 'check_circle';
      case 'error':
        return 'error';
      case 'in_progress':
        return 'hourglass_empty';
      default:
        return 'pending';
    }
  }

  openFile(path: string): void {
    if (this.electronService.isElectron) {
      this.electronService.ipcRenderer.send('open-file', path);
    }
  }
} 