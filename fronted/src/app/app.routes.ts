import { Routes } from '@angular/router';
import { Category } from './pages/category/category';
import { Dashboard } from './pages/dashboard/dashboard';
import { Home } from './pages/home/home';
import { Login } from './pages/login/login';
import { Product } from './pages/product/product';
import { Register } from './pages/register/register';
import { Wishlist } from './pages/wishlist/wishlist';
import { Search } from './pages/search/search';

export const routes: Routes = [
  { path: '', component: Home },
  { path: 'login', component: Login },
  { path: 'register', component: Register },
  { path: 'dashboard', component: Dashboard },
  { path: 'wishlist', component: Wishlist },
  { path: 'search', component: Search },
  { path: 'product/:uri', component: Product },
  { path: ':name', component: Category }
];
