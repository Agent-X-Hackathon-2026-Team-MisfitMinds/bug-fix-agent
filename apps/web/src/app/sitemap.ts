import type {MetadataRoute} from 'next';
export default function sitemap():MetadataRoute.Sitemap {const base=(process.env.NEXT_PUBLIC_APP_URL||'http://localhost:3000').replace(/\/$/,'');return ['','/how-it-works','/demo','/security','/pricing','/about','/changelog','/privacy','/terms'].map(path=>({url:base+path}))}
