import { Component, Input } from '@angular/core';

interface MetadataStatus {
  status: string;
  path?: string;
  error?: string;
}

interface MetadataItem {
  name: string;
  status: string;
  error?: string;
}

interface Download {
  title: string;
  progress: number;
  error?: string;
  status?: 'counting' | 'downloading' | 'cleaning_json' | 'warning' | 'finished' | 'error';
  msg?: string;
  total_videos?: number;
  completed_videos?: number;
  metadata_status?: {[key: string]: MetadataStatus};
}

@Component({
  selector: 'app-download-progress',
  templateUrl: './download-progress.component.html',
  styleUrls: ['./download-progress.component.scss']
})
export class DownloadProgressComponent {
  @Input() download!: Download;

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
      error: value.error
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
} 