import {initializeApp, getApps} from 'firebase/app';
import {getAuth, connectAuthEmulator} from 'firebase/auth';
import {getDatabase, connectDatabaseEmulator} from 'firebase/database';

const emulator = import.meta.env.DEV && import.meta.env.VITE_PRODUCT_EMULATOR === 'true';
const app = getApps().find(a => a.name === 'rehab-product') || initializeApp({
  apiKey: 'AIzaSyCIhOntftB7QlhPdrYNDX_DQtXY3MwL8VI',
  authDomain: 'smart-rehab-hub.firebaseapp.com',
  databaseURL: emulator ? 'https://demo-smart-rehab-product.firebaseio.com' : 'https://smart-rehab-hub-default-rtdb.asia-southeast1.firebasedatabase.app',
  projectId: emulator ? 'demo-smart-rehab-product' : 'smart-rehab-hub',
  appId: '1:863483580594:web:41e7be53c73738775079ab',
}, 'rehab-product');
export const auth = getAuth(app);
export const db = getDatabase(app);
export const root = 'rehab_v1';
if (emulator) { connectAuthEmulator(auth, 'http://127.0.0.1:19099', {disableWarnings: true}); connectDatabaseEmulator(db, '127.0.0.1', 19000); }
