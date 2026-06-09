import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { DataStreamService } from '../../services/data-stream';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: './dashboard.html',
  styleUrls: ['./dashboard.css']
})
export class Dashboard implements OnInit, OnDestroy {
  private auth = inject(AuthService);
  private streamService = inject(DataStreamService);
  private router = inject(Router);

  stats = signal<any>(null);
  lastUpdated = signal<Date | null>(null);
  private refreshTimer: any;

  ngOnInit() {
    const user = this.auth.currentUser();
    if (!user) {
      this.router.navigateByUrl('/login');
      return;
    }
    if (user.role !== 2) {
      this.router.navigateByUrl('/');
      return;
    }

    this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'DASHBOARD_STATS') {
        this.stats.set(msg);
        this.lastUpdated.set(new Date());
      }
    });

    this.load();
    this.refreshTimer = setInterval(() => this.load(), 30_000);
  }

  ngOnDestroy() {
    clearInterval(this.refreshTimer);
  }

  load() {
    this.streamService.requestDashboardStats();
  }

  maxPopularity(): number {
    const stats = this.stats();
    if (!stats?.top_products?.length) return 1;
    return stats.top_products[0].popularity;
  }

  maxCount(): number {
    const stats = this.stats();
    if (!stats?.category_counts?.length) return 1;
    return Math.max(...stats.category_counts.map((c: any) => c.count));
  }

  maxAvgPrice(): number {
    const stats = this.stats();
    if (!stats?.avg_prices?.length) return 1;
    return Math.max(...stats.avg_prices.map((c: any) => c.avg_price));
  }

  avgPriceFor(category: string): number {
    const found = this.stats()?.avg_prices?.find((a: any) => a.category === category);
    return found ? found.avg_price : 0;
  }

  catIcon(i: number): string {
    return ['laptop', 'smartphone', 'tablet', 'tv', 'watch'][i] ?? 'devices';
  }

  catClass(i: number): string {
    return ['cat-blue', 'cat-cyan', 'cat-teal', 'cat-violet', 'cat-amber'][i] ?? 'cat-blue';
  }
}
