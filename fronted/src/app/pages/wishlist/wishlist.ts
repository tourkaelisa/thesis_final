import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { DataStreamService } from '../../services/data-stream';
import { AuthService } from '../../services/auth';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';

@Component({
  selector: 'app-wishlist',
  standalone: true,
  imports: [CommonModule, RouterLink, MatIconModule, MatButtonModule, MatCardModule],
  templateUrl: './wishlist.html',
  styleUrls: ['./wishlist.css']
})
export class Wishlist implements OnInit {
  private auth = inject(AuthService);
  private router = inject(Router);

  products = signal<any[]>([]);
  loading = signal(true);

  constructor(private streamService: DataStreamService) {}

  ngOnInit() {
    const user = this.auth.currentUser();
    if (!user) {
      this.router.navigate(['/login']);
      return;
    }

    this.streamService.listenToStore().subscribe(msg => {
      if (msg.type === 'WISHLIST_DATA') {
        this.products.set(msg.products);
        this.loading.set(false);
      } else if (msg.type === 'WISHLIST_ITEM_REMOVED') {
        this.products.update(list => list.filter(p => p.id !== msg.productId));
      }
    });

    this.streamService.getWishlist();
  }

  remove(productId: string) {
    const user = this.auth.currentUser();
    if (user) {
      this.streamService.removeFromWishlist(productId);
    }
  }

  myEncode(uri: string): string {
    return encodeURIComponent(uri);
  }
}
