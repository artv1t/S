import { Connection, PublicKey } from '@solana/web3.js';

async function testOnChainFilterDirect() {
  console.log('🧪 Testing OnChain filter logic directly...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  const testTokens = [
    { name: 'USDC', address: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' },
    { name: 'USDT', address: 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB' },
    { name: 'BONK', address: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' }
  ];
  
  for (const token of testTokens) {
    console.log(`\n🪙 Testing ${token.name} (${token.address}):`);
    
    const mintPubkey = new PublicKey(token.address);
    let score = 100;
    const issues = [];
    
    try {
      console.log('  📋 Testing getAccountInfo...');
      const accountInfo = await connection.getAccountInfo(mintPubkey);
      if (accountInfo) {
        console.log('  ✅ getAccountInfo: SUCCESS');
      } else {
        console.log('  ❌ getAccountInfo: No data');
        score -= 30;
        issues.push('Account info unavailable');
      }
      
      console.log('  📊 Testing getTokenSupply...');
      const supply = await connection.getTokenSupply(mintPubkey);
      if (supply && supply.value) {
        console.log(`  ✅ getTokenSupply: ${supply.value.amount}`);
      } else {
        console.log('  ❌ getTokenSupply: Failed');
        score -= 20;
        issues.push('Supply data unavailable');
      }
      
      console.log('  👥 Testing getTokenLargestAccounts...');
      try {
        const accounts = await connection.getTokenLargestAccounts(mintPubkey);
        if (accounts && accounts.value && accounts.value.length > 0) {
          console.log(`  ✅ getTokenLargestAccounts: ${accounts.value.length} accounts`);
        } else {
          console.log('  ⚠️ getTokenLargestAccounts: No data (expected on free tier)');
          score -= 10;
          issues.push('Holder data unavailable (free RPC limitation)');
        }
      } catch (error) {
        console.log(`  ⚠️ getTokenLargestAccounts: Failed (expected on free tier) - ${error.message}`);
        score -= 10;
        issues.push('Holder data unavailable (free RPC limitation)');
      }
      
      const passed = score >= 50; // Same threshold as my fix
      console.log(`\n  📊 OnChain Filter Result:`);
      console.log(`     Score: ${score}/100`);
      console.log(`     Passed: ${passed ? '✅ YES' : '❌ NO'}`);
      console.log(`     Issues: ${issues.length > 0 ? issues.join(', ') : 'None'}`);
      
    } catch (error) {
      console.log(`  ❌ Critical error: ${error.message}`);
    }
  }
}

testOnChainFilterDirect().catch(console.error);
