import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { DataStreamService } from '../../services/data-stream';

@Component({
  selector: 'app-search',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, MatCardModule, MatButtonModule, MatIconModule],
  templateUrl: './search.html',
  styleUrls: ['./search.css']
})
export class Search implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private streamService = inject(DataStreamService);

  searchTerm = '';
  query = signal('');
  results = signal<any[]>([]);
  loading = signal(false);

  ngOnInit() {
    this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'SEARCH_RESULTS') {
        this.loading.set(false);
        this.results.set(msg.products ?? []);
      }
    });

    this.route.queryParams.subscribe(params => {
      const q = (params['q'] ?? '').trim();
      this.searchTerm = q;
      this.query.set(q);
      if (q) {
        this.loading.set(true);
        this.results.set([]);
        this.streamService.keywordSearch(q);
      } else {
        this.results.set([]);
      }
    });
  }

  submitSearch() {
    const q = this.searchTerm.trim();
    if (q) {
      this.router.navigate(['/search'], { queryParams: { q } });
    }
  }

  myEncode(uri: string): string {
    return encodeURIComponent(uri);
  }
}
