import { Routes, UrlSegment } from '@angular/router';
import { Category } from './pages/category/category';
import { Dashboard } from './pages/dashboard/dashboard';
import { Home } from './pages/home/home';
import { Login } from './pages/login/login';
import { Product } from './pages/product/product';
import { Register } from './pages/register/register';
import { Wishlist } from './pages/wishlist/wishlist';
import { Search } from './pages/search/search';

// Έγκυρες κατηγορίες·// Επιτρέπουμε δυναμικά routing μόνο για τις κατηγορίες που ξέρουμε, 
// αποφεύγοντας το σύγκρουση με το wildcard.
const KNOWN_CATEGORIES = ['laptops', 'mobiles', 'tablets', 'tvs', 'smartwatches', 'desktops', 'monitors', 'headphones', 'consoles'];

// Ταιριάζει το /:name μόνο όταν είναι γνωστή κατηγορία (αλλιώς null → δοκιμάζεται το επόμενο route).
export function categoryMatcher(segments: UrlSegment[]) {
  if (segments.length === 1 && KNOWN_CATEGORIES.includes(segments[0].path)) {
    return { consumed: segments, posParams: { name: segments[0] } };
  }
  return null;
}

export const routes: Routes = [
  { path: '', component: Home },
  { path: 'login', component: Login },
  { path: 'register', component: Register },
  { path: 'dashboard', component: Dashboard },
  { path: 'wishlist', component: Wishlist },
  { path: 'search', component: Search },
  { path: 'product/:uri', component: Product },
  { matcher: categoryMatcher, component: Category },
  // Άγνωστο URL → αρχική σελίδα.
  { path: '**', redirectTo: '' }
];
