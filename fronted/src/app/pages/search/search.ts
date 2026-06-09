import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { DataStreamService } from '../../services/data-stream';

interface Interpreted {
  category?: string | null;
  brands?: string[];
  priceMin?: number | null;
  priceMax?: number | null;
  specs?: { [k: string]: { min: number | null; max: number | null } };
  definition?: string | null;
  colors?: string[];
  os?: string | null;
  cpu?: string | null;
  releaseYear?: number | null;
  releaseFrom?: number | null;
  sort?: string | null;
  relaxedSpecs?: boolean;
}

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
  interpreted = signal<Interpreted>({});
  loading = signal(false);

  private readonly SPEC_LABELS: { [k: string]: string } = {
    ram: 'RAM (GB)',
    storage: 'Αποθήκευση (GB)',
    screen_size: 'Οθόνη (")',
    battery: 'Μπαταρία (mAh)',
    refresh_rate: 'Ρυθμός ανανέωσης (Hz)',
    camera_main_mp: 'Κάμερα (MP)',
    weight: 'Βάρος (kg)',
  };

  private readonly SORT_LABELS: { [k: string]: string } = {
    price_asc: 'φθηνότερα πρώτα',
    price_desc: 'ακριβότερα πρώτα',
    newest: 'νεότερα πρώτα',
  };

  sortLabel(key?: string | null): string {
    return key ? (this.SORT_LABELS[key] ?? key) : '';
  }

  ngOnInit() {
    this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'SEMANTIC_RESULTS') {
        this.loading.set(false);
        this.results.set(msg.products ?? []);
        this.interpreted.set(msg.interpreted ?? {});
      }
    });

    // Κάθε αλλαγή του ?q= ξανατρέχει την αναζήτηση (π.χ. refresh, νέο ερώτημα).
    this.route.queryParams.subscribe(params => {
      const q = (params['q'] ?? '').trim();
      this.searchTerm = q;
      this.query.set(q);
      if (q) {
        this.loading.set(true);
        this.results.set([]);
        this.streamService.semanticSearch(q);
      } else {
        this.results.set([]);
        this.interpreted.set({});
      }
    });
  }

  submitSearch() {
    const q = this.searchTerm.trim();
    if (q) {
      this.router.navigate(['/search'], { queryParams: { q } });
    }
  }

  hasFilters(i: Interpreted): boolean {
    return !!(i.category || (i.brands && i.brands.length) ||
      i.priceMin != null || i.priceMax != null ||
      i.definition || (i.specs && Object.keys(i.specs).length) ||
      (i.colors && i.colors.length) || i.os || i.cpu ||
      i.releaseYear != null || i.releaseFrom != null || i.sort);
  }

  specChips(i: Interpreted): { label: string; text: string }[] {
    if (!i.specs) return [];
    return Object.entries(i.specs).map(([key, range]) => {
      const label = this.SPEC_LABELS[key] ?? key;
      let text = '';
      if (range.min != null && range.max != null) {
        text = `${Math.round(range.min)}–${Math.round(range.max)}`;
      } else if (range.min != null) {
        text = `≥ ${Math.round(range.min)}`;
      } else if (range.max != null) {
        text = `≤ ${Math.round(range.max)}`;
      }
      return { label, text };
    });
  }

  myEncode(uri: string): string {
    return encodeURIComponent(uri);
  }
}
