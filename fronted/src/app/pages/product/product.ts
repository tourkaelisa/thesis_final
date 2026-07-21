import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { DataStreamService } from '../../services/data-stream';
import { AuthService } from '../../services/auth';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-product',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatButtonModule, MatIconModule, RouterLink],
  templateUrl: './product.html',
  styleUrls: ['./product.css']
})
export class Product implements OnInit {
  auth = inject(AuthService);

  product = signal<any>(null);
  recommendations = signal<any[]>([]);
  wishlisted = signal<boolean>(false);

  private currentUri = '';

  constructor(
    private route: ActivatedRoute,
    private streamService: DataStreamService
  ) {}

  ngOnInit() {
    this.streamService.listenToStore().subscribe(message => {
      if (message.type === 'RECOMMENDATIONS_UPDATED') {
        this.recommendations.set(message.products);
      } else if (message.type === 'PRODUCT_DETAILS') {
        this.product.set(message.product);
        if (message.product?.isWishlisted !== undefined) {
          this.wishlisted.set(message.product.isWishlisted);
        }
      } else if (message.type === 'WISHLIST_UPDATED') {
        this.wishlisted.set(message.isWishlisted);
      }
    });

    this.route.params.subscribe(params => {
      let productUri = decodeURIComponent(params['uri']);
      if (productUri.includes('%')) {
        productUri = decodeURIComponent(productUri);
      }
      this.currentUri = productUri;
      this.wishlisted.set(false);

      setTimeout(() => {
        this.streamService.requestRecommendations(productUri);
        this.streamService.getProductDetails(productUri);
      }, 300);
    });
  }

  addToWishlist() {
    const p = this.product();
    if (p) {
      this.streamService.addToWishlist(p.id ?? this.currentUri);
    }
  }

  myEncode(uri: string): string {
    return encodeURIComponent(uri);
  }
}
