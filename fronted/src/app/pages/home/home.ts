import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { DataStreamService } from '../../services/data-stream';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, MatButtonModule, MatIconModule],
  templateUrl: './home.html',
  styleUrls: ['./home.css']
})
export class Home implements OnInit {
  private auth = inject(AuthService);

  searchTerm = '';
  popularProducts = signal<any[]>([]);
  personalizedProducts = signal<any[]>([]);

  private readonly POPULAR_CACHE_KEY = 'popularProducts';
  private personalizedCacheKey(userId: number): string {
    return `personalizedProducts_${userId}`;
  }

  constructor(private router: Router, private streamService: DataStreamService) {}

  ngOnInit() {
    const user = this.auth.currentUser();

    // Άμεση εμφάνιση από cache (αν υπάρχει) — ενημερώνεται με φρέσκα δεδομένα μόλις έρθουν.
    const cachedPopular = this.readCache(this.POPULAR_CACHE_KEY);
    if (cachedPopular.length) {
      this.popularProducts.set(cachedPopular);
    }

    if (user) {
      const cachedRecs = this.readCache(this.personalizedCacheKey(user.id));
      if (cachedRecs.length) {
        this.personalizedProducts.set(cachedRecs);
      }
    }

    this.streamService.listenToStore().subscribe(message => {
      if (message.type === 'POPULAR_PRODUCTS') {
        this.popularProducts.set(message.products);
        this.writeCache(this.POPULAR_CACHE_KEY, message.products);
      } else if (message.type === 'PERSONALIZED_RECOMMENDATIONS') {
        this.personalizedProducts.set(message.products);
        if (user) {
          this.writeCache(this.personalizedCacheKey(user.id), message.products);
        }
      }
    });

    this.streamService.requestPopularProducts();

    if (user) {
      this.streamService.requestPersonalizedRecommendations();
    }
  }

  private readCache(key: string): any[] {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  private writeCache(key: string, value: any[]): void {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // localStorage μη διαθέσιμο (π.χ. private mode) — απλώς το αγνοούμε.
    }
  }

  myEncode(uri: string): string {
    return encodeURIComponent(uri);
  }

  searchProducts(): void {
    const query = this.searchTerm.trim();
    if (query) {
      this.router.navigate(['/search'], { queryParams: { q: query } });
    }
  }
}
