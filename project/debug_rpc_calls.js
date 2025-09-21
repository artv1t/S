import { Connection, PublicKey } from '@solana/web3.js';

const rpcEndpoints = [
  'https://solana.drpc.org',
  'https://api.mainnet-beta.solana.com',
  'https://solana-mainnet.g.alchemy.com/v2/demo',
  'https://rpc.helius.xyz/?api-key=demo'
];

async function testRPCCalls() {
  console.log('🔍 Testing RPC calls for OnChain filter debugging...\n');
  
  const testTokens = [
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', // USDC
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB', // USDT
    'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' // BONK
  ];
  
  for (const endpoint of rpcEndpoints) {
    console.log(`\n📡 Testing RPC endpoint: ${endpoint.replace(/api-key=[\w-]+/gi, 'api-key=***')}`);
    
    try {
      const connection = new Connection(endpoint, {
        commitment: 'processed',
        confirmTransactionInitialTimeout: 5000
      });
      
      console.log('  ✅ Testing getSlot...');
      const healthStart = Date.now();
      const slot = await connection.getSlot();
      console.log(`     Result: slot ${slot}, Latency: ${Date.now() - healthStart}ms`);
      
      for (const tokenAddress of testTokens) {
        console.log(`\n  🪙 Testing token: ${tokenAddress}`);
        const mintPubkey = new PublicKey(tokenAddress);
        
        try {
          console.log('     Testing getAccountInfo...');
          const accountStart = Date.now();
          const accountInfo = await connection.getAccountInfo(mintPubkey);
          console.log(`     ✅ Success: ${accountInfo ? 'Data received' : 'No data'}, Latency: ${Date.now() - accountStart}ms`);
        } catch (error) {
          console.log(`     ❌ getAccountInfo failed: ${error.message}`);
        }
        
        try {
          console.log('     Testing getTokenSupply...');
          const supplyStart = Date.now();
          const supply = await connection.getTokenSupply(mintPubkey);
          console.log(`     ✅ Success: ${supply?.value?.amount || 'No supply'}, Latency: ${Date.now() - supplyStart}ms`);
        } catch (error) {
          console.log(`     ❌ getTokenSupply failed: ${error.message}`);
        }
        
        try {
          console.log('     Testing getTokenLargestAccounts...');
          const accountsStart = Date.now();
          const accounts = await connection.getTokenLargestAccounts(mintPubkey);
          console.log(`     ✅ Success: ${accounts?.value?.length || 0} accounts, Latency: ${Date.now() - accountsStart}ms`);
        } catch (error) {
          console.log(`     ❌ getTokenLargestAccounts failed: ${error.message}`);
        }
      }
      
    } catch (error) {
      console.log(`  ❌ RPC endpoint failed: ${error.message}`);
    }
  }
}

testRPCCalls().catch(console.error);
