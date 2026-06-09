import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
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
export class Home implements OnInit, OnDestroy {
  private auth = inject(AuthService);

  searchTerm = '';
  slides = signal<any[]>([]);
  activeSlide = signal(0);
  personalizedProducts = signal<any[]>([]);
  private timer: any;

  private readonly POPULAR_CACHE_KEY = 'popularSlides';
  private personalizedCacheKey(userId: number): string {
    return `personalizedProducts_${userId}`;
  }

  categories = [
    { name: 'Laptops',       route: '/laptops',       description: 'Performance, εργασία, gaming και φορητότητα.' },
    { name: 'Mobiles',       route: '/mobiles',       description: 'Smartphones με καθαρή σύγκριση χαρακτηριστικών.' },
    { name: 'Tablets',       route: '/tablets',       description: 'Ελαφριές συσκευές για διάβασμα, media και δουλειά.' },
    { name: 'Τηλεοράσεις',  route: '/tvs',           description: 'Μεγάλες οθόνες και εικόνα για κάθε χώρο.' },
    { name: 'Smartwatches',  route: '/smartwatches',  description: 'Wearables για υγεία, ειδοποιήσεις και καθημερινότητα.' }
  ];

  constructor(private router: Router, private streamService: DataStreamService) {}

  ngOnInit() {
    const user = this.auth.currentUser();

    // Άμεση εμφάνιση από cache (αν υπάρχει) — ενημερώνεται με φρέσκα δεδομένα μόλις έρθουν.
    const cachedSlides = this.readCache(this.POPULAR_CACHE_KEY);
    if (cachedSlides.length) {
      this.slides.set(cachedSlides);
      this.startTimer();
    }

    if (user) {
      const cachedRecs = this.readCache(this.personalizedCacheKey(user.id));
      if (cachedRecs.length) {
        this.personalizedProducts.set(cachedRecs);
      }
    }

    this.streamService.listenToStore().subscribe(message => {
      if (message.type === 'POPULAR_PRODUCTS') {
        this.slides.set(message.slides);
        this.writeCache(this.POPULAR_CACHE_KEY, message.slides);
        this.startTimer();
      } else if (message.type === 'PERSONALIZED_RECOMMENDATIONS') {
        this.personalizedProducts.set(message.products);
        if (user) {
          this.writeCache(this.personalizedCacheKey(user.id), message.products);
        }
      }
    });

    this.streamService.requestPopularProducts();

    if (user) {
      this.streamService.requestPersonalizedRecommendations(user.id);
    }
  }

  ngOnDestroy() {
    clearInterval(this.timer);
  }

  private startTimer() {
    clearInterval(this.timer);
    this.timer = setInterval(() => {
      this.activeSlide.update(i => (i + 1) % this.slides().length);
    }, 4000);
  }

  goToSlide(index: number) {
    this.activeSlide.set(index);
    this.startTimer();
  }

  prevSlide() {
    this.activeSlide.update(i => (i - 1 + this.slides().length) % this.slides().length);
    this.startTimer();
  }

  nextSlide() {
    this.activeSlide.update(i => (i + 1) % this.slides().length);
    this.startTimer();
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
