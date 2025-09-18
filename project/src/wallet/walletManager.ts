import { Keypair, PublicKey, Connection, Transaction, LAMPORTS_PER_SOL } from '@solana/web3.js';
import { getAssociatedTokenAddress, createAssociatedTokenAccountInstruction, TOKEN_PROGRAM_ID } from '@solana/spl-token';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { config } from '../config/index.js';
import logger from '../utils/logger.js';

interface WalletInfo {
  publicKey: string;
  balance: number;
  tokenAccounts: Map<string, number>;
  lastUpdated: number;
  nonce: number;
  isActive: boolean;
}

interface WalletMetrics {
  totalWallets: number;
  activeWallets: number;
  totalBalance: number;
  averageBalance: number;
  lastBalanceUpdate: number;
  nonceErrors: number;
  transactionCount: number;
}

/**
 * High-security wallet management system
 * Handles multiple wallets, nonce management, and secure key storage
 */
export class WalletManager {
  private wallets = new Map<string, Keypair>();
  private walletInfo = new Map<string, WalletInfo>();
  private connection: Connection;
  private balanceUpdateInterval: NodeJS.Timeout | null = null;
  private nonceCache = new Map<string, number>();
  private readonly WALLET_DIR = './wallets';
  private readonly BACKUP_DIR = './wallets/backup';
  private readonly BALANCE_UPDATE_INTERVAL = 30000; // 30 seconds
  private readonly MIN_SOL_BALANCE = 0.01; // Minimum SOL for transactions

  constructor(connection: Connection) {
    this.connection = connection;
    this.ensureDirectories();
    this.loadWallets();
    this.startBalanceMonitoring();
  }

  /**
   * Ensure wallet directories exist with proper permissions
   */
  private ensureDirectories(): void {
    const dirs = [this.WALLET_DIR, this.BACKUP_DIR];
    
    for (const dir of dirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true, mode: 0o700 }); // Owner only
        logger.info(`📁 Created secure wallet directory: ${dir}`);
      } else {
        // Ensure proper permissions
        fs.chmodSync(dir, 0o700);
      }
    }
  }

  /**
   * Load wallets from secure storage
   */
  private loadWallets(): void {
    try {
      // Load primary wallet if specified
      if (config.walletPrivateKeyPath && fs.existsSync(config.walletPrivateKeyPath)) {
        const primaryWallet = this.loadWalletFromFile(config.walletPrivateKeyPath, 'primary');
        if (primaryWallet) {
          logger.info(`🔑 Loaded primary wallet: ${primaryWallet.publicKey.toString()}`);
        }
      }

      // Load additional wallets from wallet directory
      if (fs.existsSync(this.WALLET_DIR)) {
        const files = fs.readdirSync(this.WALLET_DIR);
        const walletFiles = files.filter(f => f.endsWith('.json') && f !== 'primary.json');
        
        for (const file of walletFiles) {
          const filePath = path.join(this.WALLET_DIR, file);
          const walletName = path.basename(file, '.json');
          this.loadWalletFromFile(filePath, walletName);
        }
      }

      logger.info(`💼 Loaded ${this.wallets.size} wallets total`);
      
      // Initialize wallet info for all loaded wallets
      this.initializeWalletInfo();
      
    } catch (error) {
      logger.error('❌ Failed to load wallets:', error);
      throw new Error('Wallet loading failed');
    }
  }

  /**
   * Load wallet from encrypted file
   */
  private loadWalletFromFile(filePath: string, name: string): Keypair | null {
    try {
      // Check file permissions
      const stats = fs.statSync(filePath);
      if ((stats.mode & 0o077) !== 0) {
        logger.warn(`⚠️ Wallet file ${filePath} has insecure permissions, fixing...`);
        fs.chmodSync(filePath, 0o600); // Owner read/write only
      }

      const data = fs.readFileSync(filePath, 'utf8');
      let keyData: number[];

      try {
        const parsed = JSON.parse(data);
        
        // Handle different wallet file formats
        if (Array.isArray(parsed)) {
          keyData = parsed;
        } else if (parsed.privateKey) {
          keyData = parsed.privateKey;
        } else if (parsed.secretKey) {
          keyData = parsed.secretKey;
        } else {
          throw new Error('Invalid wallet file format');
        }
      } catch (parseError) {
        // Try to decrypt if it's encrypted
        if (config.walletPassphrase) {
          keyData = this.decryptWalletData(data, config.walletPassphrase);
        } else {
          throw parseError;
        }
      }

      const keypair = Keypair.fromSecretKey(new Uint8Array(keyData));
      this.wallets.set(name, keypair);
      
      return keypair;
    } catch (error) {
      logger.error(`❌ Failed to load wallet ${name}:`, error);
      return null;
    }
  }

  /**
   * Decrypt wallet data using passphrase
   */
  private decryptWalletData(encryptedData: string, passphrase: string): number[] {
    try {
      const [ivHex, encryptedHex] = encryptedData.split(':');
      const iv = Buffer.from(ivHex, 'hex');
      const encrypted = Buffer.from(encryptedHex, 'hex');
      
      const key = crypto.scryptSync(passphrase, 'salt', 32);
      const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
      
      let decrypted = decipher.update(encrypted, undefined, 'utf8');
      decrypted += decipher.final('utf8');
      
      return JSON.parse(decrypted);
    } catch (error) {
      throw new Error('Failed to decrypt wallet data - check passphrase');
    }
  }

  /**
   * Initialize wallet info for all loaded wallets
   */
  private initializeWalletInfo(): void {
    for (const [name, keypair] of this.wallets.entries()) {
      this.walletInfo.set(name, {
        publicKey: keypair.publicKey.toString(),
        balance: 0,
        tokenAccounts: new Map(),
        lastUpdated: 0,
        nonce: 0,
        isActive: true
      });
    }
  }

  /**
   * Start balance monitoring for all wallets
   */
  private startBalanceMonitoring(): void {
    this.balanceUpdateInterval = setInterval(async () => {
      await this.updateAllBalances();
    }, this.BALANCE_UPDATE_INTERVAL);

    // Initial balance update
    this.updateAllBalances();
  }

  /**
   * Update balances for all wallets
   */
  private async updateAllBalances(): Promise<void> {
    const promises = Array.from(this.wallets.keys()).map(name => 
      this.updateWalletBalance(name)
    );

    await Promise.allSettled(promises);
  }

  /**
   * Update balance for specific wallet
   */
  private async updateWalletBalance(walletName: string): Promise<void> {
    const keypair = this.wallets.get(walletName);
    const info = this.walletInfo.get(walletName);
    
    if (!keypair || !info) return;

    try {
      const balance = await this.connection.getBalance(keypair.publicKey);
      const solBalance = balance / LAMPORTS_PER_SOL;
      
      info.balance = solBalance;
      info.lastUpdated = Date.now();
      
      // Check for low balance warning
      if (solBalance < this.MIN_SOL_BALANCE) {
        logger.warn(`⚠️ Low balance warning for wallet ${walletName}: ${solBalance.toFixed(6)} SOL`);
      }
      
      // Update token accounts
      await this.updateTokenAccounts(walletName);
      
    } catch (error) {
      logger.error(`Failed to update balance for wallet ${walletName}:`, error);
    }
  }

  /**
   * Update token accounts for wallet
   */
  private async updateTokenAccounts(walletName: string): Promise<void> {
    const keypair = this.wallets.get(walletName);
    const info = this.walletInfo.get(walletName);
    
    if (!keypair || !info) return;

    try {
      const tokenAccounts = await this.connection.getParsedTokenAccountsByOwner(
        keypair.publicKey,
        { programId: TOKEN_PROGRAM_ID }
      );

      info.tokenAccounts.clear();
      
      for (const account of tokenAccounts.value) {
        const mintAddress = account.account.data.parsed.info.mint;
        const amount = parseFloat(account.account.data.parsed.info.tokenAmount.uiAmount || '0');
        
        if (amount > 0) {
          info.tokenAccounts.set(mintAddress, amount);
        }
      }
      
    } catch (error) {
      logger.error(`Failed to update token accounts for wallet ${walletName}:`, error);
    }
  }

  /**
   * Get primary wallet keypair
   */
  getPrimaryWallet(): Keypair | null {
    return this.wallets.get('primary') || null;
  }

  /**
   * Get wallet by name
   */
  getWallet(name: string): Keypair | null {
    return this.wallets.get(name) || null;
  }

  /**
   * Get all wallet names
   */
  getWalletNames(): string[] {
    return Array.from(this.wallets.keys());
  }

  /**
   * Get wallet balance
   */
  getWalletBalance(walletName: string): number {
    const info = this.walletInfo.get(walletName);
    return info?.balance || 0;
  }

  /**
   * Get wallet token balance
   */
  getTokenBalance(walletName: string, mintAddress: string): number {
    const info = this.walletInfo.get(walletName);
    return info?.tokenAccounts.get(mintAddress) || 0;
  }

  /**
   * Get next nonce for wallet
   */
  async getNextNonce(walletName: string): Promise<number> {
    const keypair = this.wallets.get(walletName);
    if (!keypair) throw new Error(`Wallet ${walletName} not found`);

    try {
      // Get current nonce from cache or fetch from blockchain
      let currentNonce = this.nonceCache.get(walletName);
      
      if (currentNonce === undefined) {
        const accountInfo = await this.connection.getAccountInfo(keypair.publicKey);
        currentNonce = 0; // AccountInfo doesn't have nonce property
        this.nonceCache.set(walletName, currentNonce);
      }

      const nextNonce = currentNonce + 1;
      this.nonceCache.set(walletName, nextNonce);
      
      return nextNonce;
    } catch (error) {
      logger.error(`Failed to get nonce for wallet ${walletName}:`, error);
      throw error;
    }
  }

  /**
   * Increment nonce after successful transaction
   */
  incrementNonce(walletName: string): void {
    const current = this.nonceCache.get(walletName) || 0;
    this.nonceCache.set(walletName, current + 1);
    
    const info = this.walletInfo.get(walletName);
    if (info) {
      info.nonce = current + 1;
    }
  }

  /**
   * Create new wallet
   */
  async createWallet(name: string, encrypt = true): Promise<string> {
    if (this.wallets.has(name)) {
      throw new Error(`Wallet ${name} already exists`);
    }

    const keypair = Keypair.generate();
    const filePath = path.join(this.WALLET_DIR, `${name}.json`);
    
    try {
      // Save wallet to file
      const keyData = Array.from(keypair.secretKey);
      let dataToSave: string;
      
      if (encrypt && config.walletPassphrase) {
        dataToSave = this.encryptWalletData(keyData, config.walletPassphrase);
      } else {
        dataToSave = JSON.stringify(keyData);
      }
      
      fs.writeFileSync(filePath, dataToSave, { mode: 0o600 });
      
      // Add to memory
      this.wallets.set(name, keypair);
      this.walletInfo.set(name, {
        publicKey: keypair.publicKey.toString(),
        balance: 0,
        tokenAccounts: new Map(),
        lastUpdated: 0,
        nonce: 0,
        isActive: true
      });
      
      // Create backup
      await this.backupWallet(name);
      
      logger.info(`✅ Created new wallet: ${name} (${keypair.publicKey.toString()})`);
      return keypair.publicKey.toString();
      
    } catch (error) {
      logger.error(`Failed to create wallet ${name}:`, error);
      throw error;
    }
  }

  /**
   * Encrypt wallet data
   */
  private encryptWalletData(keyData: number[], passphrase: string): string {
    const key = crypto.scryptSync(passphrase, 'salt', 32);
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
    
    let encrypted = cipher.update(JSON.stringify(keyData), 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    return iv.toString('hex') + ':' + encrypted;
  }

  /**
   * Backup wallet to secure location
   */
  private async backupWallet(name: string): Promise<void> {
    const sourcePath = path.join(this.WALLET_DIR, `${name}.json`);
    const backupPath = path.join(this.BACKUP_DIR, `${name}_${Date.now()}.json`);
    
    try {
      fs.copyFileSync(sourcePath, backupPath);
      fs.chmodSync(backupPath, 0o600);
      logger.info(`💾 Wallet ${name} backed up to ${backupPath}`);
    } catch (error) {
      logger.error(`Failed to backup wallet ${name}:`, error);
    }
  }

  /**
   * Get associated token account address
   */
  async getAssociatedTokenAccount(walletName: string, mintAddress: string): Promise<PublicKey> {
    const keypair = this.wallets.get(walletName);
    if (!keypair) throw new Error(`Wallet ${walletName} not found`);

    return await getAssociatedTokenAddress(
      new PublicKey(mintAddress),
      keypair.publicKey
    );
  }

  /**
   * Create associated token account if needed
   */
  async createAssociatedTokenAccountIfNeeded(
    walletName: string, 
    mintAddress: string
  ): Promise<PublicKey> {
    const keypair = this.wallets.get(walletName);
    if (!keypair) throw new Error(`Wallet ${walletName} not found`);

    const associatedTokenAccount = await this.getAssociatedTokenAccount(walletName, mintAddress);
    
    try {
      // Check if account exists
      const accountInfo = await this.connection.getAccountInfo(associatedTokenAccount);
      
      if (!accountInfo) {
        // Create the account
        const transaction = new Transaction().add(
          createAssociatedTokenAccountInstruction(
            keypair.publicKey, // payer
            associatedTokenAccount, // associated token account
            keypair.publicKey, // owner
            new PublicKey(mintAddress) // mint
          )
        );
        
        const signature = await this.connection.sendTransaction(transaction, [keypair]);
        await this.connection.confirmTransaction(signature);
        
        logger.info(`✅ Created associated token account for ${mintAddress}`);
      }
      
      return associatedTokenAccount;
    } catch (error) {
      logger.error(`Failed to create associated token account:`, error);
      throw error;
    }
  }

  /**
   * Get wallet metrics
   */
  getMetrics(): WalletMetrics {
    const wallets = Array.from(this.walletInfo.values());
    const activeWallets = wallets.filter(w => w.isActive);
    const totalBalance = wallets.reduce((sum, w) => sum + w.balance, 0);
    
    return {
      totalWallets: wallets.length,
      activeWallets: activeWallets.length,
      totalBalance,
      averageBalance: wallets.length > 0 ? totalBalance / wallets.length : 0,
      lastBalanceUpdate: Math.max(...wallets.map(w => w.lastUpdated)),
      nonceErrors: 0, // Would track nonce errors
      transactionCount: 0 // Would track total transactions
    };
  }

  /**
   * Get wallet info
   */
  getWalletInfo(walletName: string): WalletInfo | null {
    return this.walletInfo.get(walletName) || null;
  }

  /**
   * Get all wallet info
   */
  getAllWalletInfo(): Map<string, WalletInfo> {
    return new Map(this.walletInfo);
  }

  /**
   * Check if wallet has sufficient balance
   */
  hasSufficientBalance(walletName: string, requiredAmount: number): boolean {
    const balance = this.getWalletBalance(walletName);
    return balance >= requiredAmount + this.MIN_SOL_BALANCE; // Keep minimum for fees
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    if (this.balanceUpdateInterval) {
      clearInterval(this.balanceUpdateInterval);
    }
    
    // Clear sensitive data from memory
    this.wallets.clear();
    this.walletInfo.clear();
    this.nonceCache.clear();
  }
}