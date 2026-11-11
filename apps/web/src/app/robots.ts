import type {MetadataRoute} from 'next';
export default function robots():MetadataRoute.Robots {return {rules:{userAgent:'*',allow:'/',disallow:['/dashboard','/auth/','/api/']},sitemap:`${(process.env.NEXT_PUBLIC_APP_URL||'http://localhost:3000').replace(/\/$/,'')}/sitemap.xml`}}
